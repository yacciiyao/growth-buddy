# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import ssl
import threading
import time
import wave
from dataclasses import dataclass
from datetime import datetime
from time import mktime
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import websocket
from wsgiref.handlers import format_date_time

from app.infra.ylogger import ylogger


class AudioFormatError(Exception):
    """音频格式不符合要求时抛出"""


class SpeechError(Exception):
    """ASR/TTS 调用失败时抛出"""


@dataclass
class _AsrResult:
    text: str = ""
    error: Optional[str] = None
    segments: dict[int, str] | None = None  # sn -> 文本片段


def _build_ws_url(app_id: str, api_key: str, api_secret: str) -> str:
    """
    构造讯飞 ASR WebSocket URL
    """
    host = "ws-api.xfyun.cn"
    path = "/v2/iat"
    url = f"wss://{host}{path}"

    now = datetime.now()
    date = format_date_time(mktime(now.timetuple()))

    signature_origin = f"host: {host}\n"
    signature_origin += f"date: {date}\n"
    signature_origin += f"GET {path} HTTP/1.1"

    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature_sha = base64.b64encode(signature_sha).decode("utf-8")

    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature_sha}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")

    params: Dict[str, Any] = {
        "authorization": authorization,
        "date": date,
        "host": host,
    }
    return f"{url}?{urlencode(params)}"


def _extract_pcm_from_wav(wav_bytes: bytes) -> bytes:
    bio = io.BytesIO(wav_bytes)
    try:
        with wave.open(bio, "rb") as wf:
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            if nchannels != 1:
                raise AudioFormatError(f"只支持单声道，当前 nchannels={nchannels}")
            if sampwidth != 2:
                raise AudioFormatError(f"只支持 16bit 采样，当前 sampwidth={sampwidth}")
            if framerate != 16000:
                raise AudioFormatError(f"需要采样率 16000Hz，当前 framerate={framerate}")
            pcm = wf.readframes(wf.getnframes())
    except wave.Error as e:
        raise AudioFormatError(f"WAV 文件解析失败: {e}") from e
    return pcm


class XfyunAsrClient:
    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        sslopt: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._app_id = app_id
        self._api_key = api_key
        self._api_secret = api_secret
        self._sslopt = sslopt or {"cert_reqs": ssl.CERT_NONE}

    def recognize(self, wav_bytes: bytes, timeout: int = 30) -> str:
        """
        同步识别：
        - 输入：16k 单声道 16bit PCM 的 WAV 字节
        - 输出：中文文本
        """
        pcm_bytes = _extract_pcm_from_wav(wav_bytes)
        ws_url = _build_ws_url(self._app_id, self._api_key, self._api_secret)

        result = _AsrResult(segments={})
        done_event = threading.Event()

        def on_message(ws: websocket.WebSocketApp, message: str) -> None:
            try:
                data = json.loads(message)
                code = data.get("code", -1)
                if code != 0:
                    err_msg = data.get("message", "unknown error")
                    sid = data.get("sid", "")
                    msg = f"ASR 失败: sid={sid}, code={code}, message={err_msg}"
                    ylogger.error(msg)
                    result.error = msg
                    done_event.set()
                    ws.close()
                    return

                result_dict = data.get("data", {}).get("result", {}) or {}
                sn = int(result_dict.get("sn", 0))
                pgs = result_dict.get("pgs")
                rg = result_dict.get("rg")

                ws_segs = result_dict.get("ws", []) or []
                piece = "".join(
                    (cw.get("w") or "")
                    for seg in ws_segs
                    for cw in (seg.get("cw") or [])
                )

                if result.segments is None:
                    result.segments = {}

                # 讯飞 IAT：pgs='rpl' 表示替换模式，rg 给出需要替换的 sn 范围。
                if pgs == "rpl" and isinstance(rg, (list, tuple)) and len(rg) == 2:
                    try:
                        rg0, rg1 = int(rg[0]), int(rg[1])
                        for k in list(result.segments.keys()):
                            if rg0 <= k <= rg1:
                                result.segments.pop(k, None)
                    except Exception:  # noqa: BLE001
                        pass

                result.segments[sn] = piece
                result.text = "".join(result.segments[k] for k in sorted(result.segments))
            except Exception as e:  # noqa: BLE001
                ylogger.exception("ASR on_message 异常: %s", e)
                result.error = str(e)
                done_event.set()
                ws.close()

        def on_error(ws: websocket.WebSocketApp, error: Exception) -> None:
            ylogger.error("ASR WebSocket 错误: %s", error)
            result.error = str(error)
            done_event.set()

        def on_close(ws: websocket.WebSocketApp, code: int, msg: str) -> None:
            ylogger.info("ASR WebSocket 关闭: code=%s, msg=%s", code, msg)

        def on_open(ws: websocket.WebSocketApp) -> None:
            def run() -> None:
                try:
                    frame_size = 8000
                    interval = 0.04
                    status = 0  # 0: first, 1: middle, 2: last

                    bio = io.BytesIO(pcm_bytes)

                    while True:
                        buf = bio.read(frame_size)
                        if not buf:
                            status = 2

                        if status == 0:
                            data = {
                                "common": {"app_id": self._app_id},
                                "business": {
                                    "domain": "iat",
                                    "language": "zh_cn",
                                    "accent": "mandarin",
                                    "vinfo": 1,
                                    "vad_eos": 10000,
                                },
                                "data": {
                                    "status": 0,
                                    "format": "audio/L16;rate=16000",
                                    "audio": base64.b64encode(buf).decode("utf-8"),
                                    "encoding": "raw",
                                },
                            }
                            ws.send(json.dumps(data))
                            status = 1
                        elif status == 1:
                            data = {
                                "data": {
                                    "status": 1,
                                    "format": "audio/L16;rate=16000",
                                    "audio": base64.b64encode(buf).decode("utf-8"),
                                    "encoding": "raw",
                                }
                            }
                            ws.send(json.dumps(data))
                        elif status == 2:
                            data = {
                                "data": {
                                    "status": 2,
                                    "format": "audio/L16;rate=16000",
                                    "audio": base64.b64encode(buf or b"").decode("utf-8"),
                                    "encoding": "raw",
                                }
                            }
                            ws.send(json.dumps(data))
                            time.sleep(0.5)
                            break

                        time.sleep(interval)

                except Exception as e:  # noqa: BLE001
                    ylogger.exception("ASR 发送线程异常: %s", e)
                    result.error = str(e)
                finally:
                    done_event.set()
                    ws.close()

            threading.Thread(target=run, name="xfyun-asr-send", daemon=True).start()

        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        ws.on_open = on_open

        ws_thread = threading.Thread(
            target=ws.run_forever,
            kwargs={"sslopt": self._sslopt},
            name="xfyun-asr-ws",
            daemon=True,
        )
        ws_thread.start()

        done_event.wait(timeout=timeout)
        ws.close()
        ws_thread.join(timeout=2)

        if result.error:
            raise SpeechError(result.error)

        return result.text.strip()
