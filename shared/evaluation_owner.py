"""Single cooperating local evaluator; no distributed lease or database migration."""
from contextlib import contextmanager
import fcntl
from pathlib import Path


@contextmanager
def evaluation_owner(path):
    lock_path = Path(str(Path(path).resolve()) + '.runner.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('An evaluation owner already holds this metrics database') from None
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    # Keep the lock inode so concurrent processes cannot lock different files.
