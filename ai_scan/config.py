"""Config storage for ai-scan.

Config lives outside the source tree at ~/.ai-scan/config.json so that
re-installing or updating the tool never touches the user's settings.
"""
import json
from pathlib import Path

APP_DIR = Path.home() / ".ai-scan"
CONFIG_PATH = APP_DIR / "config.json"
LOG_DIR = APP_DIR / "logs"

DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_MAX_SIZE_MB = 10


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"設定ファイルが見つかりません: {CONFIG_PATH}\n"
            "先に setup_wizard.py を実行してセットアップを行ってください。"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("model", DEFAULT_MODEL)
    data.setdefault("max_size_mb", DEFAULT_MAX_SIZE_MB)
    for key in ("watch_dir", "gemini_api_key"):
        if not data.get(key):
            raise ValueError(f"設定ファイルに '{key}' がありません: {CONFIG_PATH}")
    return data


def save_config(data: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    CONFIG_PATH.chmod(0o600)
