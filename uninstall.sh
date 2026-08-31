#!/usr/bin/env bash
# Uninstaller for ai-scan.
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/harada4atsushi/ai-scan/main/uninstall.sh)"
set -euo pipefail

APP_DIR="$HOME/.ai-scan"
PLIST_PATH="$HOME/Library/LaunchAgents/com.aiscan.watcher.plist"
LABEL="com.aiscan.watcher"

echo "=== 自動ドキュメント解析ツール アンインストーラー ==="

if [[ -f "$PLIST_PATH" ]]; then
  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  rm -f "$PLIST_PATH"
  echo "バックグラウンドサービスを停止・削除しました。"
fi

if [[ -t 0 ]]; then
  read -r -p "設定・ログを含む $APP_DIR を完全に削除しますか？ [y/N]: " confirm
else
  confirm="N"
fi
if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
  rm -rf "$APP_DIR"
  echo "$APP_DIR を削除しました。"
else
  echo "$APP_DIR は残しました（アプリ本体とログイン時自動起動のみ解除済み）。"
fi

echo "アンインストールが完了しました。"
