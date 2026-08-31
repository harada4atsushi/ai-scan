"""Gemini-backed PDF -> Markdown(+LaTeX) conversion."""
import io
import time

PROMPT = """あなたは文書解析の専門家です。添付されたPDFドキュメントの内容を余さず抽出し、Markdown形式のドキュメントに変換してください。

要件:
- 見出し・箇条書き・表などの構造は、できる限りMarkdown記法（#, -, |table|など）で再現すること
- 数式は LaTeX 記法で記述すること（インライン数式は $...$ 、独立した数式ブロックは $$...$$ を使用）
- 図表のキャプションや脚注も可能な限り含めること
- ページ番号やヘッダー/フッターの繰り返しなど、内容の理解に不要なノイズは省いてよい
- 出力は Markdown 本文のみとし、前置きや説明、コードブロックでの囲みなど余計な装飾は含めないこと
"""

_ACTIVE_WAIT_TIMEOUT_SEC = 120
_ACTIVE_POLL_INTERVAL_SEC = 2


def convert_pdf_to_markdown(data: bytes, filename: str, api_key: str, model: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    # Upload from an in-memory buffer, not the file path: the caller has
    # already read the bytes with retry handling for cloud-synced folders
    # (iCloud Drive/Dropbox/OneDrive), and re-reading via a path here would
    # risk hitting the same file-coordination lock again inside the SDK.
    uploaded = client.files.upload(
        file=io.BytesIO(data),
        config=types.UploadFileConfig(mime_type="application/pdf", display_name=filename),
    )

    deadline = time.time() + _ACTIVE_WAIT_TIMEOUT_SEC
    while uploaded.state.name == "PROCESSING" and time.time() < deadline:
        time.sleep(_ACTIVE_POLL_INTERVAL_SEC)
        uploaded = client.files.get(name=uploaded.name)

    if uploaded.state.name != "ACTIVE":
        raise RuntimeError(
            f"Gemini側でのファイル処理が完了しませんでした (state={uploaded.state.name})"
        )

    try:
        response = client.models.generate_content(
            model=model,
            contents=[uploaded, PROMPT],
        )
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Geminiからの応答が空でした")
    return text
