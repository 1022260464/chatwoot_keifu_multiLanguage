from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    glitchtip_dsn: str = Field(default="", alias="GLITCHTIP_DSN")
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(default=0.0, alias="SENTRY_TRACES_SAMPLE_RATE")

    llm_provider: str = Field(default="", alias="LLM_PROVIDER")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")

    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    database_url: str = Field(default="", alias="DATABASE_URL")
    rag_provider: str = Field(default="memory", alias="RAG_PROVIDER")
    db_host: str = Field(default="", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="", alias="DB_NAME")
    db_user: str = Field(default="", alias="DB_USER")
    db_pass: str = Field(default="", alias="DB_PASS")
    knowledge_schema: str = Field(default="public", alias="KNOWLEDGE_SCHEMA")
    knowledge_table_name: str = Field(default="knowledge_chunks", alias="KNOWLEDGE_TABLE_NAME")

    chatwoot_base_url: str = Field(default="", alias="CHATWOOT_BASE_URL")
    chatwoot_account_id: str = Field(default="", alias="CHATWOOT_ACCOUNT_ID")
    chatwoot_api_access_token: str = Field(default="", alias="CHATWOOT_API_ACCESS_TOKEN")
    chatwoot_bot_agent_id: str = Field(default="", alias="CHATWOOT_BOT_AGENT_ID")
    chatwoot_default_assignee_id: str = Field(default="", alias="CHATWOOT_DEFAULT_ASSIGNEE_ID")
    chatwoot_open_on_incoming: bool = Field(default=False, alias="CHATWOOT_OPEN_ON_INCOMING")
    chatwoot_language_source: Literal["detect", "inbox"] = Field(
        default="detect",
        alias="CHATWOOT_LANGUAGE_SOURCE",
    )
    chatwoot_inbox_language_map: dict[str, str] = Field(
        default_factory=dict,
        alias="CHATWOOT_INBOX_LANGUAGE_MAP",
    )
    chatwoot_website_token_language_map: dict[str, str] = Field(
        default_factory=dict,
        alias="CHATWOOT_WEBSITE_TOKEN_LANGUAGE_MAP",
    )

    admin_webhook_url: str = Field(default="", alias="ADMIN_WEBHOOK_URL")
    admin_webhook_token: str = Field(default="", alias="ADMIN_WEBHOOK_TOKEN")
    dashboard_api_token: str = Field(default="", alias="DASHBOARD_API_TOKEN")

    translation_private_note_enabled: bool = Field(default=False, alias="TRANSLATION_PRIVATE_NOTE_ENABLED")
    translation_provider: str = Field(default="pygtrans", alias="TRANSLATION_PROVIDER")
    translation_target_lang: str = Field(default="zh-CN", alias="TRANSLATION_TARGET_LANG")
    translation_skip_chinese: bool = Field(default=True, alias="TRANSLATION_SKIP_CHINESE")
    translation_min_text_length: int = Field(default=2, alias="TRANSLATION_MIN_TEXT_LENGTH")
    translation_outgoing_enabled: bool = Field(default=False, alias="TRANSLATION_OUTGOING_ENABLED")
    translation_default_user_lang: str = Field(default="", alias="TRANSLATION_DEFAULT_USER_LANG")
    translation_timeout_seconds: int = Field(default=8, alias="TRANSLATION_TIMEOUT_SECONDS")
    pygtrans_proxy: str = Field(default="", alias="PYGTRANS_PROXY")
    public_reply_fallback_language: Literal["en", "vi"] = Field(
        default="vi",
        alias="PUBLIC_REPLY_FALLBACK_LANGUAGE",
    )

    rag_min_confidence: float = Field(default=0.62, alias="RAG_MIN_CONFIDENCE")
    semantic_cache_threshold: float = Field(default=0.95, alias="SEMANTIC_CACHE_THRESHOLD")
    max_context_chunks: int = Field(default=4, alias="MAX_CONTEXT_CHUNKS")

    @property
    def error_reporting_dsn(self) -> str:
        return self.glitchtip_dsn or self.sentry_dsn

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if not all([self.db_host, self.db_name, self.db_user, self.db_pass]):
            return ""
        return (
            f"postgresql://{self.db_user}:{self.db_pass}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
