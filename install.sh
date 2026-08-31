#!/usr/bin/env bash
# One-shot installer for ai-scan.
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/harada4atsushi/ai-scan/main/install.sh)"
#
# Use the bash -c "$(...)" form, not `curl ... | install.sh`: this script
# runs an interactive setup wizard, and piping into bash would leave the
# wizard's stdin pointed at the tail of this very script instead of the
# keyboard. bash -c "$(...)" fully captures curl's output first, so the
# script runs with the real terminal as stdin.
set -euo pipefail

GITHUB_OWNER="harada4atsushi"
GITHUB_REPO="ai-scan"
BRANCH="main"

APP_DIR="$HOME/.ai-scan"
SRC_DIR="$APP_DIR/app"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="$APP_DIR/logs"
PLIST_PATH="$HOME/Library/LaunchAgents/com.aiscan.watcher.plist"
LABEL="com.aiscan.watcher"

echo "=== 自動ドキュメント解析ツール インストーラー ==="

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "このツールはmacOS専用です。" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 が見つかりません。先に Python 3.9 以上をインストールしてください（例: brew install python3）。" >&2
  exit 1
fi

PY_VERSION="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
PY_MAJOR="$(echo "$PY_VERSION" | cut -d. -f1)"
PY_MINOR="$(echo "$PY_VERSION" | cut -d. -f2)"
if [[ "$PY_MAJOR" -lt 3 || ( "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 9 ) ]]; then
  echo "Python 3.9 以上が必要です（検出: $PY_VERSION）。" >&2
  exit 1
fi

mkdir -p "$APP_DIR" "$LOG_DIR"

echo "ソースを取得しています..."
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
curl -fsSL "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/archive/refs/heads/${BRANCH}.tar.gz" -o "$TMP_DIR/src.tar.gz"
tar xzf "$TMP_DIR/src.tar.gz" -C "$TMP_DIR"
EXTRACTED_DIR="$(find "$TMP_DIR" -maxdepth 1 -type d -name "${GITHUB_REPO}-*")"
rm -rf "$SRC_DIR"
mv "$EXTRACTED_DIR" "$SRC_DIR"

echo "Python仮想環境を準備しています..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SRC_DIR/requirements.txt"

echo
echo "--- 初期設定 ---"
# When this installer itself was run as `curl ... | bash`, fd 0 is the pipe
# carrying the script source, not the keyboard. Force the interactive wizard
# to read from the real terminal so its prompts don't consume leftover
# script bytes instead of user input.
if exec 3</dev/tty 2>/dev/null; then
  exec 3<&-
  "$VENV_DIR/bin/python3" "$SRC_DIR/setup_wizard.py" < /dev/tty
else
  echo "対話端末が見つかりません。ターミナルから直接 install.sh を実行し直してください。" >&2
  exit 1
fi

echo
echo "バックグラウンドサービスを登録しています..."
cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${VENV_DIR}/bin/python3</string>
        <string>-m</string>
        <string>ai_scan.watcher</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SRC_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/stderr.log</string>
</dict>
</plist>
PLIST

launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load -w "$PLIST_PATH"

echo
echo "セットアップが完了しました。"
echo "監視は既にバックグラウンドで開始されています（ログイン時にも自動起動します）。"
echo
echo "ログ:            $LOG_DIR/stdout.log"
echo "設定ファイル:      $APP_DIR/config.json"
echo "設定変更後の反映:  launchctl kickstart -k gui/\$(id -u)/${LABEL}"
echo "アンインストール:  bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/${BRANCH}/uninstall.sh)\""
