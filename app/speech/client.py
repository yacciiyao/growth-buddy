# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import asyncio
import ssl
from typing import Any, Dict

import certifi

from app.infra.config import settings
from app.speech.asr_xfyun import XfyunAsrClient
from app.speech.tts_xfyun import XfyunTtsClient


class SpeechClient:
    """
    语音服务统一入口：
    - asr(wav_bytes) -> 文本
    - tts(text) -> PCM 字节
    """

    def __init__(self) -> None:
        app_id = settings.XFYUN_APPID
        api_key = settings.XFYUN_APIKEY
        api_secret = settings.XFYUN_APISECRET

        if not (app_id and api_key and api_secret):
            raise ValueError("讯飞配置未完整设置，请检查 XFYUN_APPID/XFYUN_API_KEY/XFYUN_API_SECRET")

        if getattr(settings, "ENV", "dev") == "production":
            sslopt: Dict[str, Any] = {
                "cert_reqs": ssl.CERT_REQUIRED,
                "ca_certs": certifi.where(),
            }
        else:
            sslopt = {
                "cert_reqs": ssl.CERT_NONE,
            }

        self._asr = XfyunAsrClient(
            app_id=app_id,
            api_key=api_key,
            api_secret=api_secret,
            sslopt=sslopt,
        )
        self._tts = XfyunTtsClient(
            app_id=app_id,
            api_key=api_key,
            api_secret=api_secret,
            sslopt=sslopt,
        )

    async def asr(self, wav_bytes: bytes) -> str:
        """语音识别"""
        return await asyncio.to_thread(self._asr.recognize, wav_bytes)

    async def tts(self, text: str) -> bytes:
        """文本转语音"""
        return await asyncio.to_thread(self._tts.synthesize, text)


    async def tts_stream(self, text: str, *, cancel_event: asyncio.Event | None = None):
        """
        流式 TTS：返回一个异步迭代器，按分片产出 PCM bytes（16k,16bit,mono）,底层仍然是 websocket-client 的同步实现，通过线程 + asyncio.Queue 桥接
        """
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _on_chunk(chunk: bytes) -> None:
            loop.call_soon_threadsafe(q.put_nowait, chunk)

        def _run() -> None:
            try:
                self._tts.synthesize_stream(text, on_chunk=_on_chunk, should_cancel=(cancel_event.is_set if cancel_event else None))
                loop.call_soon_threadsafe(q.put_nowait, None)
            except Exception as e:  # noqa: BLE001
                loop.call_soon_threadsafe(q.put_nowait, e)
                loop.call_soon_threadsafe(q.put_nowait, None)

        # 在后台线程运行同步 TTS WebSocket
        asyncio.create_task(asyncio.to_thread(_run))

        while True:
            item = await q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item
