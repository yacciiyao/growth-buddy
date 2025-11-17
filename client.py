# -*- coding: utf-8 -*-
# @File: client.py
# @Author: yaccii
# @Time: 2025-11-17 13:52
# @Description:
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模拟智能玩具终端，通过 MQTT 发送一段语音给 Smart Buddy 服务器，
并接收回复语音，保存为本地 WAV 文件。

使用前先确认：
1）服务端 MQTT 网关已启动（run_mqtt_gateway.py）
2）数据库中已有 child_id 对应的儿童
3）有一段 16kHz/16bit/mono 的 WAV 文件用于测试
"""
from __future__ import annotations

import argparse
import os
import threading
import time
import wave
from typing import Optional

import paho.mqtt.client as mqtt


def load_and_check_wav(path: str) -> bytes:
    """读取 WAV 文件并校验为 16k / 单声道 / 16bit。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"WAV 文件不存在: {path}")

    with wave.open(path, "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()

        if nchannels != 1:
            raise ValueError(f"需要单声道(channels=1), 当前 channels={nchannels}")
        if sampwidth != 2:
            raise ValueError(f"需要 16bit 采样宽度(sampwidth=2), 当前 sampwidth={sampwidth}")
        if framerate != 16000:
            raise ValueError(f"需要采样率 16000Hz, 当前 framerate={framerate}")

        frames = wf.readframes(wf.getnframes())

    # 这里返回完整的 WAV 文件字节，而不是裸 PCM
    with open(path, "rb") as f:
        return f.read()


class MqttVoiceClient:
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        device_sn: str,
        timeout: int = 30,
    ) -> None:
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._device_sn = device_sn
        self._timeout = timeout

        self._client = mqtt.Client(
            client_id=f"test-client-{int(time.time())}",
            clean_session=True,
        )

        self._reply_event = threading.Event()
        self._reply_bytes: Optional[bytes] = None

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message


    def _on_connect(self, client: mqtt.Client, userdata, flags, rc) -> None:  # type: ignore[override]
        if rc == 0:
            print(f"[MQTT] 连接成功 {self._broker_host}:{self._broker_port}")
        else:
            print(f"[MQTT] 连接失败 rc={rc}")

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:  # type: ignore[override]
        topic = msg.topic
        payload = msg.payload
        print(f"[MQTT] 收到消息: topic={topic}, bytes={len(payload)}")

        expected_topic = f"toy/{self._device_sn}/voice/reply"
        if topic != expected_topic:
            print(f"[MQTT] 非预期 topic, 忽略: {topic}")
            return

        self._reply_bytes = payload
        self._reply_event.set()


    def send_and_wait_reply(self, wav_bytes: bytes) -> bytes:
        """发送语音请求并阻塞等待回复 WAV 字节。"""
        request_topic = f"toy/{self._device_sn}/voice/request"
        reply_topic = f"toy/{self._device_sn}/voice/reply"
        # 连接 broker
        self._client.connect(self._broker_host, self._broker_port, keepalive=60)

        # 订阅回复 topic
        self._client.subscribe(reply_topic)
        print(f"[MQTT] 订阅: {reply_topic}")

        # 启动网络循环线程
        self._client.loop_start()

        try:
            # 发送请求
            print(f"[MQTT] 发布语音请求: topic={request_topic}, bytes={len(wav_bytes)}")
            self._client.publish(request_topic, wav_bytes)

            # 等待回复
            if not self._reply_event.wait(self._timeout):
                raise TimeoutError(f"{self._timeout} 秒内未收到回复")

            if self._reply_bytes is None:
                raise RuntimeError("收到回复事件，但 payload 为空")

            print(f"[MQTT] 收到回复字节: {len(self._reply_bytes)}")
            return self._reply_bytes

        finally:
            self._client.loop_stop()
            self._client.disconnect()


def save_reply_wav(reply_bytes: bytes, output_dir: str, device_sn: str) -> str:
    """把回复 WAV 字节保存成文件，文件名带时间戳。"""
    os.makedirs(output_dir, exist_ok=True)
    ts = int(time.time())
    filename = f"reply_{device_sn}_{ts}.wav"
    full_path = os.path.join(output_dir, filename)

    with open(full_path, "wb") as f:
        f.write(reply_bytes)

    print(f"[FILE] 已保存回复音频: {full_path}")
    return full_path


def main() -> None:
    parser = argparse.ArgumentParser(description="MQTT 语音对话测试客户端")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="MQTT Broker 主机（默认：127.0.0.1）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=1883,
        help="MQTT Broker 端口（默认：1883）",
    )
    parser.add_argument(
        "--device-sn",
        type=str,
        required=True,
        help="设备序列号 device_sn（必须和服务端绑定的一致）",
    )
    parser.add_argument(
        "--input-wav",
        type=str,
        required=True,
        help="要发送的 WAV 文件路径（要求：16kHz/单声道/16bit）",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./mqtt_replies",
        help="回复 WAV 保存目录（默认：./mqtt_replies）",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="等待回复超时时间（秒，默认 30）",
    )

    args = parser.parse_args()

    wav_bytes = load_and_check_wav(args.input_wav)
    client = MqttVoiceClient(
        broker_host=args.host,
        broker_port=args.port,
        device_sn=args.device_sn,
        timeout=args.timeout,
    )

    reply_bytes = client.send_and_wait_reply(wav_bytes)
    save_reply_wav(reply_bytes, args.output_dir, args.device_sn)


if __name__ == "__main__":
    main()
