#!/usr/bin/env python3
"""Interactive setup for ai-scan.

Asks for the folder to watch, the max file size to process, and the Gemini
API key, then writes ~/.ai-scan/config.json. Safe to re-run at any time to
change settings.
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

from ai_scan import config as cfg


def prompt_watch_dir(current: str | None) -> str:
    default = current or str(Path.home() / "Documents" / "AI-Scan-Inbox")
    raw = input(f"監視するフォルダのパスを入力してください [デフォルト: {default}]: ").strip()
    path = Path(raw or default).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return str(path.resolve())


def prompt_max_size(current: float | None) -> float:
    default = current or cfg.DEFAULT_MAX_SIZE_MB
    while True:
        raw = input(f"処理するファイルサイズの上限(MB)を入力してください [デフォルト: {default}]: ").strip()
        if not raw:
            return float(default)
        try:
            value = float(raw)
        except ValueError:
            print("数値を入力してください。")
            continue
        if value <= 0:
            print("0より大きい数値を入力してください。")
            continue
        return value


def prompt_api_key(current: str | None) -> str:
    hint = "（現在の設定を維持する場合は空欄でEnter）" if current else ""
    while True:
        key = getpass.getpass(f"Gemini APIキーを入力してください{hint}（入力は非表示です）: ").strip()
        if key:
            return key
        if current:
            return current
        print("APIキーは必須です。https://aistudio.google.com/apikey で取得できます。")


def main():
    print("=== 自動ドキュメント解析ツール セットアップ ===")
    try:
        existing = cfg.load_config()
    except Exception:
        existing = {}

    watch_dir = prompt_watch_dir(existing.get("watch_dir"))
    max_size_mb = prompt_max_size(existing.get("max_size_mb"))
    api_key = prompt_api_key(existing.get("gemini_api_key"))

    data = {
        "watch_dir": watch_dir,
        "max_size_mb": max_size_mb,
        "gemini_api_key": api_key,
        "model": existing.get("model", cfg.DEFAULT_MODEL),
    }
    cfg.save_config(data)

    print(f"\n設定を保存しました: {cfg.CONFIG_PATH}")
    print(f"監視フォルダ: {watch_dir}")
    print(f"サイズ上限: {max_size_mb} MB")
    return data


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nセットアップを中断しました。")
        sys.exit(1)
