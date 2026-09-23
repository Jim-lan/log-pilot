"""Filesystem overflow stays discoverable, without an in-memory event backlog."""
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest

from shared.file_intake import FileWatcherConsumer


class FileIntakeContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ['LOGPILOT_TEST_SCRATCH'])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.consumer = FileWatcherConsumer(self.root / 'landing', self.root / 'processed', max_pending=2)
        self.addCleanup(self.consumer.close)

    def test_saturated_intake_eventually_drains_all_files_without_duplicates(self):
        for index in range(7):
            (self.consumer.source_dir / f'{index}.log').write_text(f'event {index}')
        self.consumer.fill_pending()
        self.assertEqual(len(self.consumer.pending), 2)
        seen = set()
        iterator = iter(self.consumer)
        for _ in range(7):
            source, destination = next(iterator)
            self.assertLessEqual(len(self.consumer.pending), 2)
            self.assertNotIn(source, seen)
            seen.add(source)
            shutil.move(source, destination)
        self.assertEqual(len(seen), 7)
        self.assertEqual(len(list(self.consumer.processed_dir.iterdir())), 7)
        self.assertEqual(list(self.consumer.source_dir.iterdir()), [])

    def test_atomic_publication_empty_files_and_collision_preservation(self):
        temporary = self.consumer.source_dir / 'fixture.tmp'
        temporary.write_bytes(b'')
        (self.consumer.source_dir / 'ignored.txt').write_text('ignore')
        (self.consumer.source_dir / 'directory.md').mkdir()
        self.consumer.fill_pending()
        self.assertEqual(len(self.consumer.pending), 0)
        published = temporary.with_suffix('.log')
        temporary.rename(published)
        existing = self.consumer.processed_dir / 'fixture.log'
        existing.write_text('old evidence')
        source, destination = next(iter(self.consumer))
        self.assertEqual(Path(source), published)
        self.assertNotEqual(Path(destination), existing)
        shutil.move(source, destination)
        self.assertEqual(existing.read_text(), 'old evidence')
        self.assertEqual(Path(destination).read_bytes(), b'')

    def test_restart_rediscovers_unprocessed_backlog_and_skips_disappeared_files(self):
        first = self.consumer.source_dir / 'first.log'
        first.write_text('first')
        self.consumer.fill_pending()
        first.unlink()
        second = self.consumer.source_dir / 'second.md'
        second.write_text('second')
        source, destination = next(iter(self.consumer))
        self.assertEqual(Path(source), second)
        self.consumer.close()
        restarted = FileWatcherConsumer(self.consumer.source_dir, self.consumer.processed_dir, max_pending=1)
        self.addCleanup(restarted.close)
        self.assertEqual(Path(next(iter(restarted))[0]), second)

    def test_close_wakes_idle_poll_and_limits_are_validated(self):
        waiting = FileWatcherConsumer(self.root / 'empty', self.root / 'done', poll_seconds=60)
        thread = threading.Thread(target=lambda: list(waiting))
        thread.start()
        waiting.close()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        for limit in (0, -1, 10001, True, 1.5):
            with self.assertRaises(ValueError):
                FileWatcherConsumer(self.root / 'empty', self.root / 'done', max_pending=limit)
        for interval in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                FileWatcherConsumer(self.root / 'empty', self.root / 'done', poll_seconds=interval)
