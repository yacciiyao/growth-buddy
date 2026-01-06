# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

"""语音 WebSocket 业务处理

- VAD 端点检测
- barge-in 打断
- ASR -> Safety -> LLM -> 落库
- TTS 流式播报 + 显式续播

"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.common.trace import new_trace_id, set_trace_id
from app.infra.db import SessionLocal
from app.services.text_segment import segment_text_for_tts
from app.services.voice_chat_service import VoiceChatService, _pcm_to_wav_bytes
from app.services.vad import EndpointDetector
from app.speech.client import SpeechClient
from app.speech.errors import SpeechError


logger = logging.getLogger(__name__)


@dataclass
class PlaybackContext:
    """单次播报上下文（支持显式续播）"""

    turn_id: int
    child_id: int
    session_id: int
    seq: int
    user_text: str
    reply_text: str
    reply_audio_path: str
    segments: List[str]

    seg_idx: int = 0
    pcm_buffer: bytearray = field(default_factory=bytearray)
    resume_count: int = 0

    tts_started_at_ms: Optional[int] = None
    first_audio_at_ms: Optional[int] = None


async def _safe_json_loads(s: str) -> Optional[dict]:
    try:
        data = json.loads(s)
        if isinstance(data, dict):
            return data
        return None
    except Exception:  # noqa: BLE001
        return None


class VoiceWsHandler:
    def __init__(self) -> None:
        # SpeechClient/LLM selector 等初始化成本相对高，这里做一次复用
        # 但每个连接仍会独立维护播放上下文与 DB Session。
        self._speech = None
        self._service = None

    def _get_service(self) -> VoiceChatService:
        if self._service is not None:
            return self._service
        self._speech = SpeechClient()
        self._service = VoiceChatService(speech_client=self._speech)
        return self._service

    async def run(self, ws: WebSocket, device_sn: str) -> None:
        # WebSocket 也生成 trace_id（HTTP middleware 不覆盖 WS）
        set_trace_id(new_trace_id())

        await ws.accept()
        db: Session = SessionLocal()

        service = self._get_service()
        speech = self._speech
        assert speech is not None

        detector = EndpointDetector(sample_rate=16000)
        send_lock = asyncio.Lock()

        async def send_json(payload: Dict[str, Any]):
            async with send_lock:
                await ws.send_json(payload)

        async def send_bytes(data: bytes):
            async with send_lock:
                await ws.send_bytes(data)

        current_pcm = bytearray()
        in_speech = False

        playback_ctx: Optional[PlaybackContext] = None
        playback_task: Optional[asyncio.Task] = None
        playback_cancel: Optional[asyncio.Event] = None

        async def interrupt_playback(reason: str = "user_interrupt"):
            nonlocal playback_task, playback_cancel, playback_ctx
            if playback_task is None or playback_task.done():
                return
            if playback_cancel is not None and not playback_cancel.is_set():
                playback_cancel.set()
            await send_json({
                "type": "interrupt_requested",
                "reason": reason,
                "turn_id": playback_ctx.turn_id if playback_ctx else None,
            })

        async def start_playback(ctx: PlaybackContext, *, is_resume: bool = False):
            nonlocal playback_task, playback_cancel, playback_ctx
            if playback_task is not None and not playback_task.done():
                if playback_cancel is not None and not playback_cancel.is_set():
                    playback_cancel.set()
                try:
                    await asyncio.wait_for(playback_task, timeout=0.2)
                except Exception:  # noqa: BLE001
                    pass

            playback_ctx = ctx
            playback_cancel = asyncio.Event()

            if is_resume:
                ctx.resume_count += 1
                try:
                    service.update_turn_runtime(
                        db,
                        ctx.turn_id,
                        playback_status="speaking",
                        resume_count=ctx.resume_count,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("update_turn_runtime failed")

                await send_json({
                    "type": "resume_started",
                    "turn_id": ctx.turn_id,
                    "seg_idx": ctx.seg_idx,
                })
            else:
                try:
                    service.update_turn_runtime(
                        db,
                        ctx.turn_id,
                        playback_status="speaking",
                        resume_count=ctx.resume_count,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("update_turn_runtime failed")

                await send_json({
                    "type": "turn_started",
                    "turn_id": ctx.turn_id,
                    "session_id": ctx.session_id,
                    "seq": ctx.seq,
                    "user_text": ctx.user_text,
                    "reply_text": ctx.reply_text,
                    "reply_audio_path": ctx.reply_audio_path,
                })

            async def _runner():
                nonlocal playback_ctx
                cancel_event = playback_cancel
                assert cancel_event is not None

                ctx.tts_started_at_ms = int(time.time() * 1000)
                await send_json({"type": "tts_start", "turn_id": ctx.turn_id})

                try:
                    while ctx.seg_idx < len(ctx.segments):
                        if cancel_event.is_set():
                            break

                        seg = ctx.segments[ctx.seg_idx]
                        async for chunk in speech.tts_stream(seg, cancel_event=cancel_event):
                            if not chunk:
                                continue
                            if ctx.first_audio_at_ms is None:
                                ctx.first_audio_at_ms = int(time.time() * 1000)
                            ctx.pcm_buffer.extend(chunk)
                            await send_bytes(chunk)

                        if cancel_event.is_set():
                            break
                        ctx.seg_idx += 1

                    if cancel_event.is_set():
                        await send_json({
                            "type": "tts_paused",
                            "turn_id": ctx.turn_id,
                            "seg_idx": ctx.seg_idx,
                            "can_resume": True,
                        })
                        try:
                            snap_metrics = {
                                "seg_idx": ctx.seg_idx,
                                "resume_count": ctx.resume_count,
                                "seg_count": len(ctx.segments),
                                "snapshot": True,
                            }
                            if ctx.pcm_buffer:
                                snap_wav = _pcm_to_wav_bytes(bytes(ctx.pcm_buffer))
                                service.finalize_turn_reply_audio(
                                    db,
                                    ctx.turn_id,
                                    reply_wav_bytes=snap_wav,
                                    playback_status="interrupted",
                                    metrics=snap_metrics,
                                )
                            else:
                                service.update_turn_runtime(
                                    db,
                                    ctx.turn_id,
                                    playback_status="interrupted",
                                    resume_count=ctx.resume_count,
                                    metrics=snap_metrics,
                                )
                        except Exception:  # noqa: BLE001
                            logger.exception("interrupted snapshot failed")
                        return

                    reply_wav = _pcm_to_wav_bytes(bytes(ctx.pcm_buffer))
                    metrics = {
                        "seg_count": len(ctx.segments),
                        "resume_count": ctx.resume_count,
                        "tts_ms": (int(time.time() * 1000) - (ctx.tts_started_at_ms or int(time.time() * 1000))),
                        "ttft_ms": None
                        if ctx.first_audio_at_ms is None
                        else (ctx.first_audio_at_ms - (ctx.tts_started_at_ms or ctx.first_audio_at_ms)),
                    }
                    try:
                        service.finalize_turn_reply_audio(
                            db,
                            ctx.turn_id,
                            reply_wav_bytes=reply_wav,
                            playback_status="completed",
                            metrics=metrics,
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception("finalize_turn_reply_audio failed")

                    await send_json({
                        "type": "turn_end",
                        "turn_id": ctx.turn_id,
                        "session_id": ctx.session_id,
                        "seq": ctx.seq,
                        "reply_text": ctx.reply_text,
                        "reply_audio_path": ctx.reply_audio_path,
                        "metrics": metrics,
                    })
                    await send_json({"type": "tts_end", "turn_id": ctx.turn_id})

                    playback_ctx = None
                except Exception:  # noqa: BLE001
                    logger.exception("playback runner failed")
                    try:
                        if playback_ctx is not None:
                            service.update_turn_runtime(db, playback_ctx.turn_id, playback_status="error")
                    except Exception:  # noqa: BLE001
                        pass
                    await send_json({"type": "error", "message": "playback_failed"})

            playback_task = asyncio.create_task(_runner())

        await send_json({"type": "ready", "device_sn": device_sn})

        try:
            while True:
                msg = await ws.receive()

                if msg.get("text") is not None:
                    text = msg["text"]

                    if text in ("ping", "stop", "resume"):
                        data = {"type": text}
                    else:
                        data = await _safe_json_loads(text)
                        if not data:
                            logger.info("ignore invalid control msg: %s", text[:200])
                            continue

                    mtype = data.get("type")

                    if mtype == "ping":
                        await send_json({"type": "pong"})
                        continue
                    if mtype == "resume":
                        if playback_ctx is None:
                            await send_json({"type": "resume_rejected", "reason": "no_pending"})
                            continue
                        if playback_task is not None and not playback_task.done():
                            await send_json({"type": "resume_rejected", "reason": "already_speaking"})
                            continue
                        await start_playback(playback_ctx, is_resume=True)
                        continue
                    if mtype == "stop":
                        await interrupt_playback(reason="user_stop")
                        continue

                    logger.info("ignore unknown control type: %s", mtype)
                    continue

                if msg.get("bytes") is not None:
                    chunk = msg["bytes"]

                    start, end = detector.process(chunk)

                    if start and not in_speech:
                        in_speech = True
                        current_pcm = bytearray()
                        await send_json({"type": "speech_start"})

                        await interrupt_playback(reason="barge_in")

                    if in_speech:
                        current_pcm.extend(chunk)

                    if end and in_speech:
                        in_speech = False
                        await send_json({"type": "speech_end"})

                        wav_bytes = _pcm_to_wav_bytes(bytes(current_pcm))
                        t0 = int(time.time() * 1000)
                        try:
                            draft = await service.prepare_turn(db, device_sn, wav_bytes)
                        except SpeechError as e:
                            logger.error("turn failed: %s", e)
                            await send_json({"type": "error", "message": f"speech_error: {str(e)}"})
                            continue
                        except Exception as e:  # noqa: BLE001
                            logger.exception("turn failed")
                            await send_json({"type": "error", "message": f"turn_failed: {str(e)}"})
                            continue

                        segs = segment_text_for_tts(draft.reply_text) or [draft.reply_text]

                        ctx = PlaybackContext(
                            turn_id=draft.turn_id,
                            child_id=draft.child_id,
                            session_id=draft.session_id,
                            seq=draft.seq,
                            user_text=draft.user_text,
                            reply_text=draft.reply_text,
                            reply_audio_path=draft.reply_audio_path,
                            segments=segs,
                        )

                        try:
                            service.update_turn_runtime(
                                db,
                                draft.turn_id,
                                playback_status="pending",
                                metrics={
                                    "gen_ms": int(time.time() * 1000) - t0,
                                    "seg_count": len(segs),
                                },
                            )
                        except Exception:  # noqa: BLE001
                            logger.exception("update_turn_runtime failed")

                        await start_playback(ctx, is_resume=False)

                    continue

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected: device_sn=%s", device_sn)
            if playback_cancel is not None:
                playback_cancel.set()
        finally:
            db.close()
