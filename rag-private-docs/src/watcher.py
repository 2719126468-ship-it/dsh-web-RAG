"""File watcher: auto-reindex when docs/ changes.

Uses watchdog to listen for create/modify/delete events on docs/,
debounces rapid changes (e.g. an editor saving multiple times),
and triggers an incremental reindex pass.

Usage:
  python src/watcher.py          # foreground, logs to console
  python src/watcher.py --once   # run a single reindex and exit (for testing)
"""
import argparse
import sys
import time
import threading
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
DEBOUNCE_SECONDS = 2.0
SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf", ".docx"}


class DocsWatcher(FileSystemEventHandler):
    """Triggers reindex on any supported file change, debounced."""

    def __init__(self, on_change):
        self.on_change = on_change
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _relevant(self, path: str) -> bool:
        return Path(path).suffix.lower() in SUPPORTED_SUFFIXES

    def _schedule(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_SECONDS, self.on_change)
            self._timer.daemon = True
            self._timer.start()

    def on_created(self, event):
        if not event.is_directory and self._relevant(event.src_path):
            print(f"[watch] created: {event.src_path}")
            self._schedule()

    def on_modified(self, event):
        if not event.is_directory and self._relevant(event.src_path):
            self._schedule()

    def on_deleted(self, event):
        if not event.is_directory and self._relevant(event.src_path):
            print(f"[watch] deleted: {event.src_path}")
            self._schedule()

    def on_moved(self, event):
        if not event.is_directory:
            self._schedule()


def run_reindex():
    """Wrapper so the watcher callback stays clean."""
    print("[watch] triggering reindex...")
    try:
        from indexer import IncrementalIndexer
        indexer = IncrementalIndexer()
        summary = indexer.reindex(force=False)
        print(f"[watch] done: {summary}")
    except Exception as e:
        print(f"[watch] reindex failed: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run once and exit (for testing)")
    args = parser.parse_args()

    if args.once:
        run_reindex()
        return

    if not DOCS_DIR.exists():
        print(f"[error] docs dir not found: {DOCS_DIR}")
        sys.exit(1)

    # First-time full reindex to ensure store is up to date
    print("[watch] initial reindex...")
    run_reindex()

    handler = DocsWatcher(run_reindex)
    observer = Observer()
    observer.schedule(handler, str(DOCS_DIR), recursive=True)
    observer.start()
    print(f"[watch] watching {DOCS_DIR} (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[watch] stopping...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()