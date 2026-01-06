# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket

from app.application.ws.voice_ws_handler import VoiceWsHandler
from app.api.deps import get_voice_ws_handler


router = APIRouter(tags=["voice"])


@router.websocket("/ws/voice/{device_sn}")
async def voice_ws(
    websocket: WebSocket,
    device_sn: str,
    handler: VoiceWsHandler = Depends(get_voice_ws_handler),
):
    await handler.run(websocket, device_sn)
