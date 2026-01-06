# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import math
from array import array
from dataclasses import dataclass
from typing import Tuple
import webrtcvad  # type: ignore



class BaseVad:
    def is_speech(self, pcm16le_frame: bytes, sample_rate: int) -> bool:
        raise NotImplementedError


class WebRtcVad(BaseVad):
    """WebRTC VAD 封装

    WebRTC VAD 要求 10/20/30ms 的帧长，输入为 16-bit 单声道 PCM
    """

    def __init__(self, aggressiveness: int = 2) -> None:
        if webrtcvad is None:
            raise RuntimeError("webrtcvad not installed")
        self._vad = webrtcvad.Vad(int(aggressiveness))

    def is_speech(self, pcm16le_frame: bytes, sample_rate: int) -> bool:
        return bool(self._vad.is_speech(pcm16le_frame, sample_rate))


class EnergyVad(BaseVad):
    """RMS 能量阈值 VAD（回退实现，适用于演示/原型）"""

    def __init__(self, rms_threshold: float = 500.0) -> None:
        self._thr = float(rms_threshold)

    def is_speech(self, pcm16le_frame: bytes, sample_rate: int) -> bool:
        if not pcm16le_frame:
            return False
        samples = array("h")
        samples.frombytes(pcm16le_frame)
        if not samples:
            return False
        s2 = 0.0
        for x in samples:
            s2 += float(x) * float(x)
        rms = math.sqrt(s2 / len(samples))
        return rms >= self._thr


def build_vad(
    *,
    prefer_webrtc: bool = True,
    aggressiveness: int = 2,
    rms_threshold: float = 500.0,
) -> BaseVad:
    if prefer_webrtc and webrtcvad is not None:
        return WebRtcVad(aggressiveness=aggressiveness)
    return EnergyVad(rms_threshold=rms_threshold)


@dataclass
class EndpointConfig:
    sample_rate: int = 16000
    frame_ms: int = 20
    # 连续 N 帧判定为语音，触发 speech_start
    speech_start_frames: int = 3
    # 连续 N 帧判定为静音，触发 speech_end
    speech_end_silence_frames: int = 12  # 12*20ms=240ms
    max_utterance_ms: int = 15_000


class EndpointDetector:
    """流式端点检测器

    将任意长度的 PCM 分片累积为固定帧长，并输出 (speech_start, speech_end) 标记
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        *,
        frame_ms: int = 20,
        prefer_webrtc: bool = True,
        aggressiveness: int = 2,
        rms_threshold: float = 500.0,
        speech_start_frames: int = 3,
        speech_end_silence_frames: int = 12,
        max_utterance_ms: int = 15_000,
    ) -> None:
        self._vad = build_vad(
            prefer_webrtc=prefer_webrtc,
            aggressiveness=aggressiveness,
            rms_threshold=rms_threshold,
        )
        self._cfg = EndpointConfig(
            sample_rate=int(sample_rate),
            frame_ms=int(frame_ms),
            speech_start_frames=int(speech_start_frames),
            speech_end_silence_frames=int(speech_end_silence_frames),
            max_utterance_ms=int(max_utterance_ms),
        )

        self._buf = bytearray()
        self._in_speech = False
        self._speech_run = 0
        self._silence_run = 0
        self._utter_ms = 0

    @property
    def frame_bytes(self) -> int:
        # 16-bit mono
        return int(self._cfg.sample_rate * (self._cfg.frame_ms / 1000.0)) * 2

    @property
    def in_speech(self) -> bool:
        return bool(self._in_speech)

    def reset(self) -> None:
        self._buf = bytearray()
        self._in_speech = False
        self._speech_run = 0
        self._silence_run = 0
        self._utter_ms = 0

    def _process_frame(self, frame: bytes) -> Tuple[bool, bool]:
        """处理一帧数据，返回 (speech_start, speech_end)"""
        start = False
        end = False

        is_speech = self._vad.is_speech(frame, self._cfg.sample_rate)
        self._utter_ms += self._cfg.frame_ms

        if is_speech:
            self._speech_run += 1
            self._silence_run = 0
        else:
            self._silence_run += 1
            self._speech_run = 0

        if not self._in_speech:
            if is_speech and self._speech_run >= self._cfg.speech_start_frames:
                self._in_speech = True
                self._silence_run = 0
                start = True
        else:
            if (not is_speech and self._silence_run >= self._cfg.speech_end_silence_frames) or (
                self._utter_ms >= self._cfg.max_utterance_ms
            ):
                self._in_speech = False
                end = True
                self._speech_run = 0
                self._silence_run = 0
                self._utter_ms = 0

        return start, end

    def process(self, pcm_chunk: bytes) -> Tuple[bool, bool]:
        """处理任意长度 PCM 字节流，返回 (speech_start, speech_end)"""
        if not pcm_chunk:
            return False, False

        self._buf.extend(pcm_chunk)
        start_any = False
        end_any = False

        fb = self.frame_bytes
        while len(self._buf) >= fb:
            frame = bytes(self._buf[:fb])
            del self._buf[:fb]
            s, e = self._process_frame(frame)
            start_any = start_any or s
            end_any = end_any or e

        return start_any, end_any
