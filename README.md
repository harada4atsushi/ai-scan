# ai-scan — 自動ドキュメント解析ツール

指定フォルダを監視し、そこに **新しくPDFが保存された瞬間だけ** Gemini APIで内容を解析して、
同じフォルダに Markdown ファイル（数式は LaTeX 記法）として保存するmacOS向けの常駐ツールです。

## できること / できないこと

- 対象は `.pdf` のみ。画像（jpg等）や他形式は無視します。
- フォルダ内に **既にあるファイル** や **監視開始前からあるPDF** は処理しません。監視中に新規保存・移動されたPDFのみが対象です。
- ファイルサイズが上限（デフォルト10MB、セットアップ時に変更可）を超える場合は解析せず、ログにスキップ記録のみ残します。
- 出力は `example.pdf` → `example.md` のように、同名・同フォルダの単一Markdownファイルです。同名の `.md` が既に存在する場合は上書きせずスキップします。
- macOSの `launchd` に登録され、ログイン時に自動起動・常駐します。

## 必要なもの

- macOS
- Python 3.9 以上（`python3 --version` で確認可能。無ければ `brew install python3`）
- Gemini APIキー（[Google AI Studio](https://aistudio.google.com/apikey) で取得）

## インストール（curl一発）

```sh
curl -fsSL https://raw.githubusercontent.com/__GITHUB_OWNER__/__GITHUB_REPO__/main/install.sh | bash
```

実行すると:

1. `~/.ai-scan/app` にソースを取得し、`~/.ai-scan/venv` に専用のPython仮想環境を作成
2. 対話式セットアップを開始し、以下を質問されます
   - 監視するフォルダのパス（デフォルト: `~/Documents/AI-Scan-Inbox`。存在しなければ自動作成）
   - 処理するファイルサイズの上限（MB、デフォルト10）
   - Gemini APIキー（非表示入力）
3. 設定を `~/.ai-scan/config.json`（本人のみ読み書き可）に保存
4. `~/Library/LaunchAgents/com.aiscan.watcher.plist` を作成し、バックグラウンドサービスとして起動・ログイン時自動起動を有効化

以降は監視フォルダにPDFを保存するだけで、自動的に同フォルダへ `.md` が生成されます。

## 設定の変更

再セットアップすればいつでも変更できます（既存の値がデフォルト候補として表示されます）。

```sh
~/.ai-scan/venv/bin/python3 ~/.ai-scan/app/setup_wizard.py
```

保存後、実行中のサービスに設定を反映させるには再起動が必要です。

```sh
launchctl kickstart -k gui/$(id -u)/com.aiscan.watcher
```

設定ファイル `~/.ai-scan/config.json` を直接編集することも可能です（`model` フィールドで使用するGeminiモデルも変更できます。デフォルトは `gemini-2.5-pro`）。

## サービスの操作

```sh
# 状態確認
launchctl list | grep com.aiscan.watcher

# 一時停止
launchctl unload ~/Library/LaunchAgents/com.aiscan.watcher.plist

# 再開
launchctl load -w ~/Library/LaunchAgents/com.aiscan.watcher.plist

# ログ確認
tail -f ~/.ai-scan/logs/stdout.log
```

## アンインストール

```sh
curl -fsSL https://raw.githubusercontent.com/__GITHUB_OWNER__/__GITHUB_REPO__/main/uninstall.sh | bash
```

サービスの停止・自動起動解除を行い、`~/.ai-scan` 一式（設定・ログ・仮想環境）を削除するか確認します。

## 注意事項

- 監視フォルダを `Documents` / `Desktop` / `Downloads` 配下にした場合、初回アクセス時にmacOSから
  「python3 にファイルへのアクセスを許可しますか」といった権限確認が表示されることがあります。
  表示された場合は「システム設定 > プライバシーとセキュリティ > ファイルとフォルダ」から許可してください。
- PDFの内容はGemini APIに送信されます。機密文書を扱う場合はご注意ください。
- 1ファイルずつ順番に処理する単純な実装です。大量のPDFを一度に投入すると処理完了まで時間がかかります。
