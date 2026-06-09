from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    sidecar_api_token: str = "change-me"
    kubeconfig: str = "/kube/config"
    k8s_context: str = ""
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    audit_db_path: str = "/data/audit/bb-8.db"
    knowledge_dir: str = "/knowledge"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
