# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import logging

from app.mqtt.gateway import MqttVoiceGateway

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

if __name__ == "__main__":
    gateway = MqttVoiceGateway()
    gateway.start()
