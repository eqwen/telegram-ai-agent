from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


def _get_path_env(name: str, default: Path) -> Path:
    raw_value = os.getenv(name)
    if not raw_value:
        return default

    path = Path(raw_value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:4b")
    database_path: Path = _get_path_env("DATABASE_PATH", BASE_DIR / "data" / "memory.sqlite3")
    max_context_messages: int = _get_int_env("MAX_CONTEXT_MESSAGES", 12)
    max_prompt_chars: int = _get_int_env("MAX_PROMPT_CHARS", 12000)
    request_timeout_seconds: int = _get_int_env("REQUEST_TIMEOUT_SECONDS", 90)
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings(telegram_bot_token=_get_required_env("TELEGRAM_BOT_TOKEN"))
