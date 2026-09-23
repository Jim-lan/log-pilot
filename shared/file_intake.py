"""Bounded local immutable-file intake; the landing directory is the backlog."""
from collections import deque
import math
import os
from pathlib import Path
import threading
import uuid


class FileWatcherConsumer:
    """Poll completed-file handoffs without accumulating filesystem events."""
    def __init__(self, source_dir='data/source/landing_zone', processed_dir='data/source/processed',
                 *, max_pending=None, poll_seconds=1.0):
        if max_pending is None:
            max_pending = int(os.getenv('LOGPILOT_INGEST_QUEUE_SIZE', '256'))
        if type(max_pending) is not int or not 1 <= max_pending <= 10000:
            raise ValueError('Ingestion queue size must be an integer from 1 to 10000')
        if not math.isfinite(poll_seconds) or poll_seconds <= 0:
            raise ValueError('Polling interval must be positive and finite')
        self.source_dir = Path(source_dir)
        self.processed_dir = Path(processed_dir)
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.max_pending = max_pending
        self.poll_seconds = poll_seconds
        self.pending = deque()
        self.stopped = threading.Event()

    def fill_pending(self):
        # Rescan only once a bounded batch has drained. Never materialize a full directory list.
        if self.pending or self.stopped.is_set():
            return
        with os.scandir(self.source_dir) as entries:
            for entry in entries:
                if self.stopped.is_set():
                    break
                if Path(entry.name).suffix in ('.log', '.md') and entry.is_file(follow_symlinks=False):
                    self.pending.append(Path(entry.path))
                    if len(self.pending) == self.max_pending:
                        break

    def __iter__(self):
        while not self.stopped.is_set():
            self.fill_pending()
            if not self.pending:
                self.stopped.wait(self.poll_seconds)
                continue
            source = self.pending.popleft()
            if source.is_symlink() or not source.is_file():
                continue
            destination = self.processed_dir / source.name
            if destination.exists():
                destination = destination.with_name(source.stem + '_' + uuid.uuid4().hex + source.suffix)
            # No size-stability heuristic: a final extension is the producer's immutable handoff.
            yield str(source), str(destination)

    def close(self):
        self.stopped.set()
        self.pending.clear()
