# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import ssl
import threading
import certifi
from dataclasses import dataclass
from datetime import datetime
from time import mktime
from typing import Any, Dict, Optional, Callable
from urllib.parse import urlencode

import websocket
from wsgiref.handlers import format_date_time

from app.infra.ylogger import ylogger
from app.speech.asr_xfyun import SpeechError


@dataclass
class _TtsResult:
    pcm_bytes: bytes = b""
    error: Optional[str] = None


def _build_ws_url(app_id: str, api_key: str, api_secret: str) -> str:
    """
    构造讯飞 TTS WebSocket URL
    """
    host = "ws-api.xfyun.cn"
    path = "/v2/tts"
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


class XfyunTtsClient:
    """
    讯飞 TTS 客户端，只负责合成
    """

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

    def synthesize(self, text: str, timeout: int = 30, should_cancel: Optional[Callable[[], bool]] = None) -> bytes:
        """
        同步合成：
        - 输入：文本
        - 输出：PCM 字节（16k,16bit,mono），末尾附加一点静音
        """
        ws_url = _build_ws_url(self._app_id, self._api_key, self._api_secret)

        result = _TtsResult()
        done_event = threading.Event()

        def on_message(ws: websocket.WebSocketApp, message: str) -> None:
            try:
                if should_cancel is not None and bool(should_cancel()):
                    done_event.set()
                    ws.close()
                    return
                data = json.loads(message)
                code = data.get("code", -1)
                if code != 0:
                    err_msg = data.get("message", "unknown error")
                    sid = data.get("sid", "")
                    msg = f"TTS 失败: sid={sid}, code={code}, message={err_msg}"
                    ylogger.error(msg)
                    result.error = msg
                    done_event.set()
                    ws.close()
                    return

                audio_data = data.get("data", {}).get("audio")
                status = data.get("data", {}).get("status")
                if audio_data:
                    chunk = base64.b64decode(audio_data)
                    result.pcm_bytes += chunk

                if status == 2:
                    done_event.set()
                    ws.close()

            except Exception as e:  # noqa: BLE001
                ylogger.exception("TTS on_message 异常: %s", e)
                result.error = str(e)
                done_event.set()
                ws.close()

        def on_error(ws: websocket.WebSocketApp, error: Exception) -> None:
            ylogger.error("TTS WebSocket 错误: %s", error)
            result.error = str(error)
            done_event.set()

        def on_close(ws: websocket.WebSocketApp, code: int, msg: str) -> None:
            ylogger.info("TTS WebSocket 关闭: code=%s, msg=%s", code, msg)

        def on_open(ws: websocket.WebSocketApp) -> None:
            def run() -> None:
                try:
                    req = {
                        "common": {"app_id": self._app_id},
                        "business": {
                            "aue": "raw",
                            "auf": "audio/L16;rate=16000",
                            "vcn": "xiaoyan",
                            "tte": "utf8",
                            "speed": 50,
                            "volume": 50,
                        },
                        "data": {
                            "status": 2,
                            "text": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
                        },
                    }
                    ws.send(json.dumps(req))
                except Exception as e:  # noqa: BLE001
                    ylogger.exception("TTS 发送线程异常: %s", e)
                    result.error = str(e)
                    done_event.set()
                    ws.close()

            threading.Thread(target=run, name="xfyun-tts-send", daemon=True).start()

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
            name="xfyun-tts-ws",
            daemon=True,
        )
        ws_thread.start()

        done_event.wait(timeout=timeout)
        ws.close()
        ws_thread.join(timeout=2)

        if result.error:
            raise SpeechError(result.error)

        pcm = result.pcm_bytes

        # 末尾加一点静音，避免声音收得太硬
        # 16k * 2 字节 ≈ 32000 字节 ≈ 1 秒
        pcm += b"\x00" * 32000

        return pcm


    def synthesize_stream(
        self,
        text: str,
        *,
        on_chunk: Callable[[bytes], None],
        should_cancel: Optional[Callable[[], bool]] = None,
        timeout: int = 30,
        tail_silence_ms: int = 120,
    ) -> None:
        """
        流式合成：
        - on_chunk(pcm_bytes) 会在收到每个音频分片时被调用
        - 适用于“边合成边播放”的低延迟链路
        说明：该方法为同步阻塞实现，建议上层用 asyncio.to_thread 包装
        """
        ws_url = _build_ws_url(self._app_id, self._api_key, self._api_secret)

        result = _TtsResult()
        done_event = threading.Event()

        def on_message(ws: websocket.WebSocketApp, message: str) -> None:
            try:
                if should_cancel is not None and bool(should_cancel()):
                    done_event.set()
                    ws.close()
                    return
                data = json.loads(message)
                code = data.get("code", -1)
                if code != 0:
                    result.error = data.get("message") or f"xfyun tts error code={code}"
                    done_event.set()
                    ws.close()
                    return

                audio_b64 = data.get("data", {}).get("audio")
                status = data.get("data", {}).get("status")

                if audio_b64:
                    chunk = base64.b64decode(audio_b64)
                    if chunk:
                        try:
                            on_chunk(chunk)
                        except Exception:  # noqa: BLE001
                            # 回调异常不应影响 WebSocket 主循环：记录错误并终止
                            result.error = "on_chunk 回调失败"
                            done_event.set()
                            ws.close()
                            return

                if status == 2:
                    done_event.set()
                    ws.close()

            except Exception as e:  # noqa: BLE001
                ylogger.exception("TTS on_message 异常: %s", e)
                result.error = str(e)
                done_event.set()
                ws.close()

        def on_error(ws: websocket.WebSocketApp, error: Exception) -> None:
            ylogger.error("TTS WebSocket 错误: %s", error)
            result.error = str(error)
            done_event.set()

        def on_open(ws: websocket.WebSocketApp) -> None:
            if should_cancel is not None and bool(should_cancel()):
                done_event.set()
                ws.close()
                return
            # 发送合成请求
            payload = {
                "common": {"app_id": self._app_id},
                "business": {
                    "aue": "raw",
                    "auf": "audio/L16;rate=16000",
                    "vcn": "xiaoyan",
                    "tte": "utf8",
                },
                "data": {
                    "status": 2,
                    "text": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
                },
            }
            ws.send(json.dumps(payload))

        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_open=on_open,
        )

        ws_thread = threading.Thread(
            target=ws.run_forever,
            kwargs={"sslopt": {"cert_reqs": ssl.CERT_REQUIRED, "ca_certs": certifi.where()}},
            daemon=True,
        )
        ws_thread.start()

        if not done_event.wait(timeout=timeout):
            ws.close()
            raise SpeechError("讯飞 TTS 超时")

        if result.error:
            raise SpeechError(result.error)

        # 附加尾部静音（避免设备播报尾部被截断）
        if tail_silence_ms > 0:
            silence = b"\x00\x00" * int(16000 * (tail_silence_ms / 1000.0))
            on_chunk(silence)
