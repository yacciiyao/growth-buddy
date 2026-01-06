# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import asyncio
from typing import Optional

import paho.mqtt.client as mqtt

from app.infra.config import settings
from app.infra.db import SessionLocal
from app.infra.ylogger import ylogger
from app.services import VoiceChatService
from app.speech.asr_xfyun import AudioFormatError, SpeechError


class MqttVoiceGateway:
    """
    MQTT 网关：
    - 订阅: toy/{device_sn}/voice/request
    - 收到 payload: 视为 16k 单声道 16bit 的 WAV 字节
    - 调用 VoiceChatService 处理一轮对话
    - 把回复 WAV 发布到: toy/{device_sn}/voice/reply
    """

    def __init__(self) -> None:
        self._broker_host: str = getattr(settings, "MQTT_BROKER_HOST", "127.0.0.1")
        self._broker_port: int = int(getattr(settings, "MQTT_BROKER_PORT", 1883))
        self._username: Optional[str] = getattr(settings, "MQTT_USERNAME", None) or None
        self._password: Optional[str] = getattr(settings, "MQTT_PASSWORD", None) or None
        self._client_id_prefix: str = getattr(settings, "MQTT_CLIENT_ID_PREFIX", "yoo-gw-")

        self._client = mqtt.Client(
            client_id=f"{self._client_id_prefix}voice",
            clean_session=True,
        )
        if self._username:
            self._client.username_pw_set(self._username, self._password or "")

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        # 语音对话核心服务
        self._voice_service = VoiceChatService()

    # ---------- 公开启动方法 ----------

    def start(self) -> None:
        ylogger.info("Connecting to MQTT broker %s:%s ...", self._broker_host, self._broker_port)
        self._client.connect(self._broker_host, self._broker_port, keepalive=60)
        ylogger.info("Connected. Start loop_forever...")
        self._client.loop_forever()

    # ---------- 回调 ----------

    def _on_connect(self, client: mqtt.Client, userdata, flags, rc) -> None:  # type: ignore[override]
        if rc == 0:
            ylogger.info("MQTT connected, subscribing to request topics...")
            topic = "toy/+/voice/request"
            client.subscribe(topic)
            ylogger.info("Subscribed: %s", topic)
        else:
            ylogger.error("MQTT connect failed, rc=%s", rc)

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:  # type: ignore[override]
        topic = msg.topic
        raw_payload = msg.payload
        if isinstance(raw_payload, (bytes, bytearray)):
            payload_bytes = bytes(raw_payload)
        else:
            payload_bytes = str(raw_payload).encode("utf-8")
        ylogger.info("Received MQTT message: topic=%s, bytes=%s", topic, len(payload_bytes))

        parts = topic.split("/")
        if len(parts) != 4 or parts[0] != "toy" or parts[2] != "voice" or parts[3] != "request":
            ylogger.warning("Ignore message with unexpected topic: %s", topic)
            return

        device_sn = parts[1]

        db = SessionLocal()
        try:
            wav_bytes: bytes = payload_bytes
            ylogger.info("Handling voice turn: device_sn=%s, wav_bytes=%s", device_sn, len(wav_bytes))

            result = asyncio.run(
                self._voice_service.handle_turn(
                    db=db,
                    device_sn=device_sn,
                    wav_bytes=wav_bytes,
                    session_id=None,
                )
            )

            reply_topic = f"toy/{device_sn}/voice/reply"
            client.publish(reply_topic, result.reply_wav_bytes)
            ylogger.info(
                "Published reply: topic=%s, bytes=%s, child_id=%s, session_id=%s, turn_id=%s",
                reply_topic,
                len(result.reply_wav_bytes),
                result.child_id,
                result.session_id,
                result.turn_id,
            )

        except AudioFormatError as e:
            ylogger.error("Failed to handle MQTT message (audio format): topic=%s, error=%s", topic, e)
        except SpeechError as e:
            ylogger.error("Failed to handle MQTT message (speech error): topic=%s, error=%s", topic, e)
        except ValueError as e:
            ylogger.error("Failed to handle MQTT message (value error): topic=%s, error=%s", topic, e)
        except Exception as e:  # noqa: BLE001
            ylogger.exception("Failed to handle MQTT message: topic=%s, error=%s", topic, e)
        finally:
            db.close()
