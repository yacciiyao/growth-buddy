# Yoo Growth Buddy (WebSocket + MQTT + Storage + Auth)

一套“设备接入 + 对话管理 + 内容安全 + 音频存储（S3）”的语音陪伴后端骨架：

- **WebSocket 语音通道**：设备/前端上行 PCM 流，服务端做 VAD 断句、ASR、LLM 生成，并流式回传 TTS PCM（支持“打断/显式续播”）。
- **MQTT 网关**（可选）：设备侧走 MQTT 时的接入示例（语音请求→服务端处理→语音回复）。
- **数据落库**：MySQL（默认 docker-compose）记录家长/儿童/设备、会话与对话轮次（turn），并记录播放状态与基础指标。
- **音频存储**：优先 S3，未配置则自动落盘并通过 `/files/*` 暴露静态访问。
- **大模型可选**：支持 DeepSeek(OpenAI 兼容)、OpenAI(ChatGPT)、本地 Ollama(OpenAI 兼容)，无配置时自动降级到 dummy。
- **登录注册**：手机号 + 验证码，JWT access_token + 可撤销 refresh_token。
- **工程化**：分层（router -> usecase -> domain/infra）、统一错误码、trace_id 日志、Alembic 迁移。

## 环境要求

- Python 3.10+（建议 3.11）
- MySQL 8.0+（推荐使用项目自带 docker-compose）
- （可选）S3（AWS S3 / MinIO；不配则落盘）
- 讯飞 ASR/TTS（需要账号与三项密钥）

## 运行步骤

1) 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) 启动 MySQL（推荐）

```bash
docker compose up -d
```

3) 配置环境变量

复制并编辑配置：

```bash
cp .env.example .env
```

至少需要填写：

- `DATABASE_URL`
- `JWT_SECRET_KEY`

根据要跑的能力补充：

- 语音 ASR/TTS：`XFYUN_APPID / XFYUN_APIKEY / XFYUN_APISECRET`
- 音频存储（可选）：`AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_S3_REGION / AWS_S3_BUCKET / AWS_S3_BASE_URL`（未配置则落盘并走 `/files/*`）
- （可选）`AWS_S3_ENDPOINT_URL`：使用 MinIO 时建议设置
- （可选）LLM：`LLM_DEFAULT_PROVIDER` 与对应 provider 的 key/base_url/model

4) 初始化数据库（推荐 Alembic）

```bash
alembic upgrade head
```

```bash
python init_db.py
```

5) 启动 Web 服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- WebSocket：`ws://127.0.0.1:8000/ws/voice/{device_sn}`
- API（示例）
  - Auth：`/auth/send_code` / `/auth/register` / `/auth/login` / `/auth/refresh` / `/auth/logout`
  - Profile：`/parents/setup`、`/parents/children/{child_id}/profile`
  - History：`/history/children/{child_id}/sessions`、`/history/sessions/{session_id}`

6) （可选）启动 MQTT 网关

```bash
python mqtt_service.py
```

> MQTT 默认订阅/发布 topic 在 `app/mqtt/gateway.py` 中，可按设备协议调整。

## Demo

- `ws_client_demo.py`：WebSocket 本地示例（便于验证通路）

## Quickstart (curl)

1) 发送验证码（固定 123456）

```bash
curl -X POST http://127.0.0.1:8000/auth/send_code \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","scene":"register"}'
```

2) 注册并拿 token

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","code":"123456"}'
```

3) 绑定儿童与设备（带 Authorization）

```bash
curl -X POST http://127.0.0.1:8000/parents/setup \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -d '{
    "child_name":"小明",
    "child_age":6,
    "child_gender":"boy",
    "child_interests":["恐龙","太空"],
    "child_forbidden_topics":["暴力"],
    "device_sn":"DEV-0001",
    "toy_name":"Buddy",
    "toy_age":"6",
    "toy_gender":"male",
    "toy_persona":"温柔耐心，会用儿童能理解的方式回答"
  }'
```

