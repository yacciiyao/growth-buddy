# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import io
import logging
import time
import wave
from dataclasses import dataclass
from datetime import datetime
import json
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infra import storage_s3
from app.domain import models
from app.domain import safety
from app.llm.model_selector import LlmModelSelector
from app.llm.registry import build_default_registry
from app.speech.asr_xfyun import AudioFormatError, SpeechError
from app.speech.client import SpeechClient

logger = logging.getLogger("yoo-growth-buddy.voice")


@dataclass
class VoiceTurnResult:
    """给 MQTT / 调用方用的结果对象"""

    child_id: int
    session_id: int
    turn_id: int
    user_text: str
    reply_text: str
    user_audio_path: str  # 相对路径（S3 key）
    reply_audio_path: str  # 相对路径（S3 key）
    reply_wav_bytes: bytes  # 回复语音的 WAV 字节


@dataclass
class VoiceTurnDraft:
    """给 WebSocket 场景用：先生成文本与落库，再由 WS 侧负责 TTS 播放与续播"""

    child_id: int
    session_id: int
    turn_id: int
    seq: int
    user_text: str
    reply_text: str
    user_audio_path: str
    reply_audio_path: str
    risk_source: Optional[str]
    risk_reason: Optional[str]
    audit_action: str
    policy_version: str


class VoiceChatService:
    """
    语音对话核心服务：
    - 输入：device_sn + wav_bytes（16k 单声道 16bit WAV）
    - 输出：本轮文本 + 语音回复 + DB 中的 session/turn 记录
    """

    def __init__(
        self,
        speech_client: Optional[SpeechClient] = None,
        llm_selector: Optional[LlmModelSelector] = None,
        max_history_turns: int = 6,
    ) -> None:
        self._speech = speech_client or SpeechClient()
        registry = build_default_registry()
        self._llm_selector = llm_selector or LlmModelSelector(registry)
        self._max_history_turns = max_history_turns

    # ---------- 对外主入口：单轮对话 ----------

    async def handle_turn(
        self,
        db: Session,
        device_sn: str,
        wav_bytes: bytes,
        session_id: Optional[int] = None,
    ) -> VoiceTurnResult:
        """
        处理一轮语音对话
        """
        # 1. 找到设备和孩子
        device, child = self._load_device_and_child(db, device_sn)

        # 2. session：如果没传就创建一个新的
        session = self._get_or_create_session(db, child, session_id)

        # 3. 本轮 seq
        seq = self._next_turn_seq(db, session.id)

        # 4. 保存孩子语音（S3）
        user_rel_path, _ = self._save_user_wav(child.id, session.id, seq, wav_bytes)

        # 5. ASR
        try:
            user_text_raw = await self._speech.asr(wav_bytes)
        except AudioFormatError as e:
            logger.error("ASR 音频格式错误: %s", e)
            raise
        except SpeechError as e:
            logger.error("ASR 识别失败: %s", e)
            raise

        user_text = (user_text_raw or "").strip()
        if not user_text:
            user_text = "（未识别到有效语音内容）"

        # 6. 安全检查（输入）
        risk_source: Optional[str] = None
        risk_reason: Optional[str] = None

        in_risk, in_reason = self._guard_child_input(user_text, child)
        if in_risk:
            risk_source = "input"
            risk_reason = in_reason
            reply_text_final = self._safe_reply(device)
        else:
            # 7. 构造 LLM messages
            messages = self._build_messages_for_llm(db, child, device, session, user_text)

            # 8. 调用 LLM
            provider, model_name, gen_cfg = self._llm_selector.select_for_child(child, task="chat")
            logger.info("调用 LLM: provider=%s, model=%s", getattr(provider, "name", "unknown"), model_name)

            reply_text_raw = await provider.chat(
                messages,
                model=model_name,
                max_tokens=int(gen_cfg.get("max_tokens", 256)),
                temperature=float(gen_cfg.get("temperature", 0.8)),
                extra_params={k: v for k, v in gen_cfg.items() if k not in ("max_tokens", "temperature")},
            )
            reply_text_raw = (reply_text_raw or "").strip()

            # 9. 安全收敛（输出）
            reply_text_candidate = self._sanitize_reply(child, reply_text_raw)
            out_risk, out_reason = self._guard_reply_output(reply_text_candidate, child)
            if out_risk:
                risk_source = "output"
                risk_reason = out_reason
                reply_text_final = self._safe_reply(device)
            else:
                reply_text_final = reply_text_candidate

        # 10. TTS
        try:
            reply_pcm = await self._speech.tts(reply_text_final)
        except SpeechError as e:
            logger.error("TTS 合成失败: %s", e)
            raise

        # 11. PCM → WAV + 上传（S3）
        reply_wav_bytes = _pcm_to_wav_bytes(reply_pcm)
        reply_rel_path, _ = self._save_reply_wav(child.id, session.id, seq, reply_wav_bytes)

        # 12. 写入 Turn（device_id 必须传）
        turn = models.Turn(
            session_id=session.id,
            device_id=device.id,
            seq=seq,
            user_text=user_text,
            reply_text=reply_text_final,
            user_audio_path=user_rel_path,
            reply_audio_path=reply_rel_path,
            risk_source=risk_source,
            risk_reason=risk_reason,
            created_at=int(time.time()),
        )
        db.add(turn)
        db.commit()
        db.refresh(turn)

        logger.info(
            "完成一轮对话: child_id=%s, session_id=%s, turn_id=%s, seq=%s",
            child.id,
            session.id,
            turn.id,
            seq,
        )

        return VoiceTurnResult(
            child_id=child.id,
            session_id=session.id,
            turn_id=turn.id,
            user_text=user_text,
            reply_text=reply_text_final,
            user_audio_path=user_rel_path,
            reply_audio_path=reply_rel_path,
            reply_wav_bytes=reply_wav_bytes,
        )


    async def prepare_turn(
        self,
        db: Session,
        device_sn: str,
        wav_bytes: bytes,
        *,
        session_id: Optional[int] = None,
        user_text_override: Optional[str] = None,
        policy_version: str = "safety_v1",
    ) -> VoiceTurnDraft:
        """WebSocket 专用：完成 ASR/LLM/安全策略与落库，但不在此处做 TTS

        - 语音上传到 S3
        - 生成 reply_text 并写入 turns 表（reply_audio_path 预置 key，便于后续上传）
        - 续播/播放由 WS 侧控制
        """

        device, child = self._load_device_and_child(db, device_sn)
        session = self._get_or_create_session(db, child, session_id)
        seq = self._next_turn_seq(db, session.id)

        # 1) 保存用户语音（S3）
        user_rel_path, _ = self._save_user_wav(child.id, session.id, seq, wav_bytes)

        # 2) ASR
        if user_text_override is not None:
            user_text_raw = user_text_override
        else:
            user_text_raw = await self._speech.asr(wav_bytes)

        user_text = (user_text_raw or "").strip() or "（未识别到有效语音内容）"

        # 3) 安全与回复生成
        risk_source: Optional[str] = None
        risk_reason: Optional[str] = None
        audit_action = "allow"

        in_risk, in_reason = self._guard_child_input(user_text, child)
        if in_risk:
            risk_source = "input"
            risk_reason = in_reason
            audit_action = "block_input"
            reply_text_final = self._safe_reply(device)
        else:
            messages = self._build_messages_for_llm(db, child, device, session, user_text)
            provider, model_name, gen_cfg = self._llm_selector.select_for_child(child, task="chat")
            reply_text_raw2 = await provider.chat(
                messages,
                model=model_name,
                max_tokens=int(gen_cfg.get("max_tokens", 256)),
                temperature=float(gen_cfg.get("temperature", 0.8)),
                extra_params={k: v for k, v in gen_cfg.items() if k not in ("max_tokens", "temperature")},
            )
            reply_text_raw2 = (reply_text_raw2 or "").strip()

            reply_text_candidate = self._sanitize_reply(child, reply_text_raw2)
            out_risk, out_reason = self._guard_reply_output(reply_text_candidate, child)
            if out_risk:
                risk_source = "output"
                risk_reason = out_reason
                audit_action = "block_output"
                reply_text_final = self._safe_reply(device)
            else:
                reply_text_final = reply_text_candidate

        # 4) 预置回复音频 key（真正上传由 WS 侧 finalize_turn 完成）
        reply_rel_path = f"children/{child.id}/sessions/{session.id}/turn_{seq}_reply.wav"

        # 5) 落库（playback_status 先置为 pending，便于续播/排障）
        turn = models.Turn(
            session_id=session.id,
            device_id=device.id,
            seq=seq,
            user_text=user_text,
            reply_text=reply_text_final,
            user_audio_path=user_rel_path,
            reply_audio_path=reply_rel_path,
            risk_flag=bool(risk_source),
            risk_source=risk_source,
            risk_reason=risk_reason,
            playback_status="pending",
            resume_count=0,
            policy_version=policy_version,
            audit_action=audit_action,
            created_at=int(time.time()),
        )
        db.add(turn)
        db.commit()
        db.refresh(turn)

        return VoiceTurnDraft(
            child_id=child.id,
            session_id=session.id,
            turn_id=turn.id,
            seq=seq,
            user_text=user_text,
            reply_text=reply_text_final,
            user_audio_path=user_rel_path,
            reply_audio_path=reply_rel_path,
            risk_source=risk_source,
            risk_reason=risk_reason,
            audit_action=audit_action,
            policy_version=policy_version,
        )


    def update_turn_runtime(
        self,
        db: Session,
        turn_id: int,
        *,
        playback_status: str,
        resume_count: Optional[int] = None,
        audit_action: Optional[str] = None,
        metrics: Optional[dict] = None,
    ) -> None:
        """更新播放态与链路指标（供 WS 流程调用）"""
        turn = db.get(models.Turn, turn_id)
        if turn is None:
            return

        turn.playback_status = playback_status
        if resume_count is not None:
            turn.resume_count = int(resume_count)
        if audit_action is not None:
            turn.audit_action = audit_action
        if metrics is not None:
            try:
                turn.metrics_json = json.dumps(metrics, ensure_ascii=False)
            except Exception:  # noqa: BLE001
                turn.metrics_json = None

        db.add(turn)
        db.commit()


    def finalize_turn_reply_audio(
        self,
        db: Session,
        turn_id: int,
        *,
        reply_wav_bytes: bytes,
        playback_status: str = "completed",
        metrics: Optional[dict] = None,
    ) -> None:
        """上传回复音频到 S3，并更新 turns 记录"""

        turn = db.get(models.Turn, turn_id)
        if turn is None:
            return

        if turn.reply_audio_path:
            storage_s3.upload_bytes(turn.reply_audio_path, reply_wav_bytes, content_type="audio/wav")

        turn.playback_status = playback_status
        if metrics is not None:
            try:
                turn.metrics_json = json.dumps(metrics, ensure_ascii=False)
            except Exception:  # noqa: BLE001
                pass

        db.add(turn)
        db.commit()


    async def handle_turn_stream(
        self,
        db: Session,
        device_sn: str,
        wav_bytes: bytes,
        *,
        on_tts_chunk,
        session_id: Optional[int] = None,
        cancel_event=None,
    ) -> VoiceTurnResult:
        """
        流式版本：
        - 与 handle_turn 相同的业务逻辑与落库
        - TTS 通过 on_tts_chunk(pcm_chunk) 逐片段回传（16k,16bit,mono PCM）
        """
        device, child = self._load_device_and_child(db, device_sn)
        session = self._get_or_create_session(db, child, session_id)
        seq = self._next_turn_seq(db, session.id)

        # 保存用户语音（S3）
        user_rel_path, _ = self._save_user_wav(child.id, session.id, seq, wav_bytes)

        # ASR
        try:
            user_text_raw = await self._speech.asr(wav_bytes)
        except AudioFormatError as e:
            logger.error("ASR 音频格式错误: %s", e)
            raise
        except SpeechError as e:
            logger.error("ASR 识别失败: %s", e)
            raise

        user_text = (user_text_raw or "").strip()
        if not user_text:
            user_text = "（未识别到有效语音内容）"

        # 输入安全检查
        risk_source: Optional[str] = None
        risk_reason: Optional[str] = None

        in_risk, in_reason = self._guard_child_input(user_text, child)
        if in_risk:
            risk_source = "input"
            risk_reason = in_reason
            reply_text_final = self._safe_reply(device)
        else:
            messages = self._build_messages_for_llm(db, child, device, session, user_text)
            provider, model_name, gen_cfg = self._llm_selector.select_for_child(child, task="chat")
            logger.info("调用 LLM: provider=%s, model=%s", getattr(provider, "name", "unknown"), model_name)

            reply_text_raw = await provider.chat(
                messages,
                model=model_name,
                max_tokens=int(gen_cfg.get("max_tokens", 256)),
                temperature=float(gen_cfg.get("temperature", 0.8)),
                extra_params={k: v for k, v in gen_cfg.items() if k not in ("max_tokens", "temperature")},
            )
            reply_text_raw = (reply_text_raw or "").strip()

            reply_text_candidate = self._sanitize_reply(child, reply_text_raw)
            out_risk, out_reason = self._guard_reply_output(reply_text_candidate, child)
            if out_risk:
                risk_source = "output"
                risk_reason = out_reason
                reply_text_final = self._safe_reply(device)
            else:
                reply_text_final = reply_text_candidate

        # TTS 流式合成：边播报边累积，用于最终落盘/上传
        reply_pcm_parts: List[bytes] = []
        try:
            async for chunk in self._speech.tts_stream(reply_text_final, cancel_event=cancel_event):
                if not chunk:
                    continue
                reply_pcm_parts.append(chunk)
                await on_tts_chunk(chunk)
        except SpeechError as e:
            logger.error("TTS 合成失败: %s", e)
            raise

        reply_pcm = b"".join(reply_pcm_parts)
        reply_wav_bytes = _pcm_to_wav_bytes(reply_pcm)

        reply_rel_path, _ = self._save_reply_wav(child.id, session.id, seq, reply_wav_bytes)

        turn = models.Turn(
            session_id=session.id,
            device_id=device.id,
            seq=seq,
            user_text=user_text,
            reply_text=reply_text_final,
            user_audio_path=user_rel_path,
            reply_audio_path=reply_rel_path,
            risk_source=risk_source,
            risk_reason=risk_reason,
            created_at=int(time.time()),
        )
        db.add(turn)
        db.commit()
        db.refresh(turn)

        return VoiceTurnResult(
            child_id=child.id,
            session_id=session.id,
            turn_id=turn.id,
            user_text=user_text,
            reply_text=reply_text_final,
            user_audio_path=user_rel_path,
            reply_audio_path=reply_rel_path,
            reply_wav_bytes=reply_wav_bytes,
        )



    def _load_device_and_child(
        self,
        db: Session,
        device_sn: str,
    ) -> tuple[models.Device, models.Child]:
        device = (
            db.query(models.Device)
            .filter(models.Device.device_sn == device_sn)
            .first()
        )
        if device is None:
            raise ValueError(f"Device not found: sn={device_sn}")

        if device.bound_child_id is None:
            raise ValueError(f"Device not bound to child: sn={device_sn}")

        child = db.query(models.Child).get(device.bound_child_id)
        if child is None:
            raise ValueError(f"Child not found: id={device.bound_child_id}")

        return device, child

    def _get_or_create_session(
        self,
        db: Session,
        child: models.Child,
        session_id: Optional[int],
    ) -> models.ChatSession:
        if session_id is not None:
            session = db.get(models.ChatSession, session_id)
            if session is None or session.child_id != child.id:
                raise ValueError("Invalid session_id for this child")
            return session

        session = models.ChatSession()
        session.child_id = child.id
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def _next_turn_seq(self, db: Session, session_id: int) -> int:
        last_seq = (
            db.query(func.max(models.Turn.seq))
            .filter(models.Turn.session_id == session_id)
            .scalar()
        )
        if last_seq is None:
            return 1
        return int(last_seq) + 1

    def _build_messages_for_llm(
        self,
        db: Session,
        child: models.Child,
        device: models.Device,
        session: models.ChatSession,
        current_user_text: str,
    ) -> List[dict]:
        interests = _split_str(child.interests)
        forbidden = _split_str(child.forbidden_topics)

        toy_name = device.toy_name or "小悠"
        toy_persona = (
            device.toy_persona
            or f"一个叫{toy_name}的温柔可爱小伙伴，会认真听小朋友说话，轻声细语，喜欢鼓励和安慰小朋友。"
        )

        system_prompt = (
            f"你是一个儿童智能语音陪伴玩具，名字叫「{toy_name}」。"
            f"你的性格设定：{toy_persona}。"
            f"说话对象是一个大约 {child.age} 岁的孩子，性别：{child.gender or '未知'}。"
            f"孩子的兴趣：{', '.join(interests) if interests else '暂时未知'}。"
            f"家长禁止谈论的话题：{', '.join(forbidden) if forbidden else '无特别限制'}。"
            "和孩子聊天时要遵守这些原则："
            "1）用简短、温柔、具体的句子，像小朋友的好朋友一样说话；"
            "2）多鼓励、多肯定，避免批评；"
            "3）遇到危险、暴力、隐私、敏感内容时婉拒，并引导到安全健康的话题；"
            "4）不要出现成人世界的复杂概念（如色情、血腥、极端政治等）；"
            "5）一定用中文回答。"
        )

        messages: List[dict] = [
            {"role": "system", "content": system_prompt},
        ]

        history_turns: List[models.Turn] = (
            db.query(models.Turn)
            .filter(models.Turn.session_id == session.id)
            .order_by(models.Turn.seq.asc())
            .all()
        )

        if len(history_turns) > self._max_history_turns:
            history_turns = history_turns[-self._max_history_turns :]

        for t in history_turns:
            if t.user_text:
                messages.append({"role": "user", "content": t.user_text})
            if t.reply_text:
                messages.append({"role": "assistant", "content": t.reply_text})

        messages.append({"role": "user", "content": current_user_text})

        return messages


    def _safe_reply(self, device: models.Device) -> str:
        toy_name = device.toy_name or "小悠"
        return (
            f"{toy_name}觉得这个话题有点不适合，"
            "我们先换个轻松的话题吧。"
            "你可以跟我说说今天有没有开心的事情，"
            "或者你喜欢的玩具、动画片、游戏～"
        )

    def _guard_child_input(self, text: str, child: models.Child) -> tuple[bool, str]:
        try:
            safety.check_child_input(text, extra_forbidden_topics=_split_str(child.forbidden_topics))
            return False, ""
        except safety.SafetyViolation as e:
            return True, e.reason

    def _guard_reply_output(self, text: str, child: models.Child) -> tuple[bool, str]:
        try:
            safety.check_reply_output(text, extra_forbidden_topics=_split_str(child.forbidden_topics))
            return False, ""
        except safety.SafetyViolation as e:
            return True, e.reason

    def _sanitize_reply(self, child: models.Child, reply_text: str) -> str:
        text = reply_text or ""

        forbidden = _split_str(child.forbidden_topics)
        risk_keywords = set(forbidden) | {
            "自杀",
            "杀人",
            "暴力",
            "色情",
            "毒品",
            "赌博",
        }

        lowered = text.lower()

        def _contains_risk() -> bool:
            for kw in risk_keywords:
                if not kw:
                    continue
                if kw.lower() in lowered:
                    return True
            return False

        if not text or _contains_risk():
            toy_name = "小悠"
            return (
                f"{toy_name}觉得这个话题有点不安全，"
                "我们先不聊这个哦。"
                "要不要跟小悠说说你今天遇到的开心事情，"
                "或者聊聊你喜欢的玩具、动画片、游戏？"
            )

        return text

    def _generate_session_title(self, db: Session, session: models.ChatSession) -> str:
        first_turn: models.Turn | None = (
            db.query(models.Turn)
            .filter(models.Turn.session_id == session.id)
            .order_by(models.Turn.seq.asc())
            .first()
        )

        if first_turn is not None:
            base_text = first_turn.user_text or first_turn.reply_text or ""
            base_text = (base_text or "").replace("\n", " ").strip()
            if base_text:
                if len(base_text) > 20:
                    base_text = base_text[:20] + "..."
                return base_text

        ts = session.created_at or int(datetime.now().timestamp())
        dt = datetime.fromtimestamp(ts)
        date_str = dt.strftime("%Y-%m-%d")
        return f"{date_str} 和小yo的聊天"

    def _save_user_wav(
        self,
        child_id: int,
        session_id: int,
        seq: int,
        wav_bytes: bytes,
    ) -> tuple[str, str]:
        """保存孩子原始语音到 S3"""
        key = f"children/{child_id}/sessions/{session_id}/turn_{seq}_user.wav"
        storage_s3.upload_bytes(key, wav_bytes, content_type="audio/wav")
        return key, key

    def _save_reply_wav(
        self,
        child_id: int,
        session_id: int,
        seq: int,
        reply_wav_bytes: bytes,
    ) -> tuple[str, str]:
        key = f"children/{child_id}/sessions/{session_id}/turn_{seq}_reply.wav"
        storage_s3.upload_bytes(key, reply_wav_bytes, content_type="audio/wav")
        return key, key

def _split_str(s: str | None) -> List[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def _pcm_to_wav_bytes(pcm: bytes, *, sample_rate: int = 16000) -> bytes:
    """
    把 16bit 单声道 PCM 包装成标准 WAV 字节
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()
