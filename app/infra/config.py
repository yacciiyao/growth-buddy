# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，从 .env / 环境变量读取"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 运行环境
    ENV: str = Field("dev", description="运行环境: dev / prod")

    # 数据库
    DATABASE_URL: str = Field(
        "mysql+pymysql://root:root@127.0.0.1:3306/growth_buddy?charset=utf8mb4",
        description="数据库连接串（MySQL），例如 mysql+pymysql://user:pass@host:3306/dbname?charset=utf8mb4",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    # 文件根目录（日志/临时文件等）
    FILE_BASE_PATH: str = Field(
        "./data",
        description="本地数据根目录（可选）",
        validation_alias=AliasChoices("FILE_BASE_PATH", "FILE_ROOT", "file_base_path"),
    )

    # MQTT
    MQTT_BROKER_HOST: str = Field(
        "127.0.0.1",
        description="MQTT broker host",
        validation_alias=AliasChoices("MQTT_BROKER_HOST", "mqtt_host"),
    )
    MQTT_BROKER_PORT: int = Field(
        1883,
        description="MQTT broker port",
        validation_alias=AliasChoices("MQTT_BROKER_PORT", "mqtt_port"),
    )
    MQTT_USERNAME: Optional[str] = Field(
        None,
        description="MQTT 用户名（可选）",
        validation_alias=AliasChoices("MQTT_USERNAME", "mqtt_username"),
    )
    MQTT_PASSWORD: Optional[str] = Field(
        None,
        description="MQTT 密码（可选）",
        validation_alias=AliasChoices("MQTT_PASSWORD", "mqtt_password"),
    )
    MQTT_CLIENT_ID_PREFIX: str = Field(
        "yoo-gw-",
        description="MQTT client_id 前缀",
        validation_alias=AliasChoices("MQTT_CLIENT_ID_PREFIX", "mqtt_client_id_prefix"),
    )

    # 讯飞语音（ASR/TTS）
    XFYUN_APPID: str = Field(
        "",
        description="讯飞 APPID（未配置时，语音能力不可用）",
        validation_alias=AliasChoices("XFYUN_APPID", "xfyun_appid"),
    )
    XFYUN_APIKEY: str = Field(
        "",
        description="讯飞 APIKey（未配置时，语音能力不可用）",
        validation_alias=AliasChoices("XFYUN_APIKEY", "xfyun_apikey"),
    )
    XFYUN_APISECRET: str = Field(
        "",
        description="讯飞 APISecret（未配置时，语音能力不可用）",
        validation_alias=AliasChoices("XFYUN_APISECRET", "xfyun_apisecret"),
    )

    # 大模型默认 provider
    LLM_DEFAULT_PROVIDER: str = Field(
        "deepseek",
        description="默认大模型 provider: deepseek / openai / ollama / dummy",
        validation_alias=AliasChoices("LLM_DEFAULT_PROVIDER", "llm_default_provider"),
    )

    # DeepSeek
    DEEPSEEK_API_KEY: Optional[str] = Field(
        None,
        description="DeepSeek API key",
        validation_alias=AliasChoices("DEEPSEEK_API_KEY", "deepseek_api_key"),
    )
    DEEPSEEK_BASE_URL: Optional[str] = Field(
        None,
        description="DeepSeek API base url，例如 https://api.deepseek.com",
        validation_alias=AliasChoices("DEEPSEEK_BASE_URL", "deepseek_base_url"),
    )
    DEEPSEEK_MODEL: str = Field(
        "deepseek-reasoner",
        description="DeepSeek 默认模型",
        validation_alias=AliasChoices("DEEPSEEK_MODEL", "deepseek_model"),
    )

    # OpenAI / ChatGPT
    OPENAI_API_KEY: Optional[str] = Field(
        None,
        description="OpenAI API key",
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    OPENAI_BASE_URL: Optional[str] = Field(
        None,
        description="OpenAI API base url（可选，自建代理时使用）",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "openai_base_url"),
    )
    OPENAI_MODEL: str = Field(
        "gpt-4o-mini",
        description="OpenAI 默认模型",
        validation_alias=AliasChoices("OPENAI_MODEL", "openai_model"),
    )

    # Ollama
    OLLAMA_BASE_URL: Optional[str] = Field(
        None,
        description="Ollama base url，例如 http://127.0.0.1:11434/v1",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "ollama_base_url"),
    )
    OLLAMA_MODEL: str = Field(
        "qwen2.5:7b-instruct",
        description="Ollama 默认模型",
        validation_alias=AliasChoices("OLLAMA_MODEL", "ollama_model"),
    )

    # 家长端简单鉴权
    ADMIN_TOKEN: Optional[str] = Field(
        None,
        description="家长管理端简单鉴权 token（占位）",
        validation_alias=AliasChoices("ADMIN_TOKEN", "admin_token"),
    )

    # S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_REGION: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_S3_BASE_URL: str = ""
    AWS_S3_ENDPOINT_URL: Optional[str] = Field(
        None,
        description="S3 endpoint url（可选）",
        validation_alias=AliasChoices("AWS_S3_ENDPOINT_URL", "aws_s3_endpoint_url"),
    )

    # Auth
    JWT_SECRET_KEY: str = Field(
        "dev-secret-change-me",
        description="JWT 签名密钥（生产务必更换）",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "jwt_secret_key"),
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        30,
        description="access_token 有效期（分钟）",
        validation_alias=AliasChoices("ACCESS_TOKEN_EXPIRE_MINUTES", "access_token_expire_minutes"),
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        7,
        description="refresh_token 有效期（天）",
        validation_alias=AliasChoices("REFRESH_TOKEN_EXPIRE_DAYS", "refresh_token_expire_days"),
    )

    # SMS
    SMS_FIXED_CODE: str = Field(
        "123456",
        description="模拟短信验证码（固定值）",
        validation_alias=AliasChoices("SMS_FIXED_CODE", "sms_fixed_code"),
    )
    OTP_TTL_SECONDS: int = Field(
        300,
        description="验证码有效期（秒）",
        validation_alias=AliasChoices("OTP_TTL_SECONDS", "otp_ttl_seconds"),
    )
    OTP_SEND_INTERVAL_SECONDS: int = Field(
        60,
        description="同手机号发送间隔（秒）",
        validation_alias=AliasChoices("OTP_SEND_INTERVAL_SECONDS", "otp_send_interval_seconds"),
    )
    OTP_MAX_VERIFY_FAILS: int = Field(
        5,
        description="验证码最大失败次数（超过后短暂锁定）",
        validation_alias=AliasChoices("OTP_MAX_VERIFY_FAILS", "otp_max_verify_fails"),
    )


settings = Settings()
