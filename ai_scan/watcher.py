"""Watch a folder and convert newly-saved PDFs to Markdown via Gemini.

Only fires on files that show up *while this process is running* (watchdog
fs events, not a directory scan), and only for .pdf files. Anything already
in the folder at startup, and any non-PDF file, is left untouched.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from . import config as cfg
from .gemini_client import convert_pdf_to_markdown

STABLE_POLL_INTERVAL_SEC = 1.0
STABLE_CHECKS_REQUIRED = 2
STABLE_WAIT_TIMEOUT_SEC = 600

READ_RETRY_ATTEMPTS = 5
READ_RETRY_DELAY_SEC = 2.0


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )
    return logging.getLogger("ai_scan")


def _is_target_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf" and not path.name.startswith(".")


def _wait_until_stable(path: Path, logger: logging.Logger) -> bool:
    """Wait until the file's size stops changing (write/copy finished).

    Returns False if the file disappeared before it stabilized.
    """
    start = time.time()
    last_size = -1
    stable_count = 0
    while time.time() - start < STABLE_WAIT_TIMEOUT_SEC:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        if size == last_size:
            stable_count += 1
            if stable_count >= STABLE_CHECKS_REQUIRED:
                return True
        else:
            stable_count = 0
            last_size = size
        time.sleep(STABLE_POLL_INTERVAL_SEC)
    logger.warning("ファイルサイズの安定待ちがタイムアウトしました。処理を続行します: %s", path)
    return True


def _read_file_robust(path: Path, logger: logging.Logger) -> bytes:
    """Read the whole file, retrying on transient OSErrors.

    Files inside iCloud Drive / Dropbox / OneDrive folders are managed by a
    sync daemon that briefly holds a file-coordination lock; reading them
    right as they finish appearing can raise OSError (e.g. errno 11,
    "Resource deadlock avoided") even though the file is already complete.
    A short retry clears this up without needing any cloud-provider-specific
    API.
    """
    last_error: OSError | None = None
    for attempt in range(1, READ_RETRY_ATTEMPTS + 1):
        try:
            return path.read_bytes()
        except OSError as e:
            last_error = e
            logger.warning(
                "ファイル読み込みに失敗（%d/%d回目。iCloud/Dropbox等の同期処理と競合した可能性）: %s (%s)",
                attempt,
                READ_RETRY_ATTEMPTS,
                path,
                e,
            )
            time.sleep(READ_RETRY_DELAY_SEC)
    assert last_error is not None
    raise last_error


class PdfHandler(FileSystemEventHandler):
    def __init__(self, config: dict, logger: logging.Logger, known_files: set[Path] | None = None):
        self.config = config
        self.logger = logger
        self._processing: set[Path] = set()
        # Files that already existed when watching started. macOS FSEvents can
        # occasionally deliver a "created" event for a file written just before
        # the watch stream was set up; this snapshot makes sure such files are
        # never treated as newly-saved, per spec (only genuinely new files fire).
        self._known_files: set[Path] = known_files or set()

    def on_created(self, event):
        if event.is_directory:
            return
        self._maybe_handle(Path(event.src_path))

    def on_moved(self, event):
        # Drag/move-into-folder (same-volume Finder moves) surfaces as a
        # "moved" event rather than "created" -- treat it the same way.
        if event.is_directory:
            return
        self._maybe_handle(Path(event.dest_path))

    def on_deleted(self, event):
        if event.is_directory:
            return
        # Once a pre-existing file is removed, a later file with the same name
        # is genuinely new and should no longer be ignored.
        self._known_files.discard(Path(event.src_path).resolve())

    def _maybe_handle(self, path: Path):
        if not _is_target_pdf(path):
            return
        resolved = path.resolve() if path.exists() else path
        if resolved in self._known_files:
            self.logger.debug("既存ファイルのイベントのため無視: %s", path)
            return
        if path in self._processing:
            return
        self._processing.add(path)
        try:
            self._handle(path)
        finally:
            self._processing.discard(path)

    def _handle(self, path: Path):
        logger = self.logger
        logger.info("新しいPDFを検出: %s", path)

        if not _wait_until_stable(path, logger):
            logger.warning("安定待ち中にファイルが消えたためスキップ: %s", path)
            return

        try:
            size = path.stat().st_size
        except FileNotFoundError:
            logger.warning("処理直前にファイルが見つからないためスキップ: %s", path)
            return

        if size == 0:
            logger.warning("スキップ（空のファイル）: %s", path)
            return

        max_bytes = float(self.config["max_size_mb"]) * 1024 * 1024
        if size > max_bytes:
            logger.warning(
                "スキップ（サイズ上限 %.1fMB を超過: %.1fMB）: %s",
                self.config["max_size_mb"],
                size / 1024 / 1024,
                path,
            )
            return

        output_path = path.with_suffix(".md")
        if output_path.exists():
            logger.info("スキップ（既に解析済み: %s が存在）: %s", output_path.name, path)
            return

        try:
            data = _read_file_robust(path, logger)
        except OSError:
            logger.exception("ファイルの読み込みに失敗しました（リトライ上限到達）: %s", path)
            return

        try:
            markdown = convert_pdf_to_markdown(
                data, path.name, self.config["gemini_api_key"], self.config.get("model", cfg.DEFAULT_MODEL)
            )
            output_path.write_text(markdown, encoding="utf-8")
            logger.info("解析完了・保存しました: %s", output_path)
        except Exception:
            logger.exception("解析に失敗しました: %s", path)


def main():
    logger = setup_logging()
    try:
        config = cfg.load_config()
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    watch_dir = Path(config["watch_dir"]).expanduser()
    if not watch_dir.is_dir():
        logger.error("監視フォルダが存在しません: %s", watch_dir)
        sys.exit(1)

    known_files = {
        p.resolve() for p in watch_dir.iterdir() if p.is_file() and _is_target_pdf(p)
    }
    if known_files:
        logger.info("監視開始時点で既に存在する%d件のPDFは対象外とします", len(known_files))

    handler = PdfHandler(config, logger, known_files=known_files)
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()
    logger.info("監視を開始しました: %s（サイズ上限 %sMB）", watch_dir, config["max_size_mb"])

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
