# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

"""WebSocket 语音客户端演示脚本

- 以二进制帧发送 16kHz/16bit/mono PCM 分片
- 接收文本帧事件（JSON）
- 接收二进制帧 TTS 音频（PCM）
- 发送控制消息：
  - {"type":"stop"} 暂停当前播报
  - {"type":"resume"} 从暂停处续播
"""


from __future__ import annotations

import argparse
import asyncio
import json
import os
import wave

import websockets


def read_wav_pcm(path: str) -> bytes:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with wave.open(path, "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
            raise ValueError("WAV 必须为 16kHz/16bit/mono")
        return wf.readframes(wf.getnframes())


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True, help="e.g. ws://127.0.0.1:8000/ws/voice/DEV001")
    parser.add_argument("--input-wav", type=str, required=True)
    parser.add_argument("--frame-ms", type=int, default=20)
    parser.add_argument("--stop-at", type=float, default=0.0, help="seconds after TTS start to send stop")
    parser.add_argument("--resume-after", type=float, default=0.0, help="seconds after stop to send resume")
    args = parser.parse_args()

    pcm = read_wav_pcm(args.input_wav)
    bytes_per_ms = 16000 * 2 // 1000  # 16kHz * 2 字节（16bit）
    frame_size = bytes_per_ms * args.frame_ms

    async with websockets.connect(args.url, max_size=50 * 1024 * 1024) as ws:
        print("Connected")

        tts_started = False
        stop_sent = False
        stop_task: asyncio.Task | None = None

        async def receiver():
            nonlocal tts_started, stop_sent, stop_task
            while True:
                msg = await ws.recv()
                if isinstance(msg, bytes):
                    # TTS 音频
                    print(f"[BIN] {len(msg)} bytes")
                else:
                    try:
                        ev = json.loads(msg)
                        print("[EV]", ev)
                        if ev.get("type") == "tts_start":
                            tts_started = True
                            if args.stop_at > 0 and not stop_sent:
                                async def _send_stop_resume() -> None:
                                    nonlocal stop_sent
                                    await asyncio.sleep(args.stop_at)
                                    await ws.send(json.dumps({"type": "stop"}))
                                    stop_sent = True
                                    if args.resume_after > 0:
                                        await asyncio.sleep(args.resume_after)
                                        await ws.send(json.dumps({"type": "resume"}))

                                stop_task = asyncio.create_task(_send_stop_resume())
                    except Exception:
                        print("[TXT]", msg)

        async def sender():
            # 以二进制帧发送 PCM
            for i in range(0, len(pcm), frame_size):
                await ws.send(pcm[i : i + frame_size])
                await asyncio.sleep(args.frame_ms / 1000.0)
            # 心跳
            while True:
                await ws.send(json.dumps({"type": "ping"}))
                await asyncio.sleep(10)

        await asyncio.gather(receiver(), sender())


if __name__ == "__main__":
    asyncio.run(main())
