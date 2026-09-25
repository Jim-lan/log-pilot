"""Abrupt evaluator exits on disposable data; no app mounts or provider calls."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shared.evaluation import EvaluationStore
from shared.evaluation_owner import evaluation_owner


def child(path, boundary):
    with evaluation_owner(path):
        store = EvaluationStore(path)
        store.start('crashed', ['a', 'b'], {'fixture': True})
        if boundary != 'roster':
            store.record('crashed', 'a', 'passed', 1, {'answer': 'fixture'})
        if boundary == 'all_cases':
            store.record('crashed', 'b', 'passed', 2, {'answer': 'fixture'})
        if boundary == 'locked':
            print('READY', flush=True)
            sys.stdin.read()
        os._exit(78)


def main():
    for boundary, passes in [('roster', 0), ('one_case', 1), ('all_cases', 2), ('locked', 1)]:
        with tempfile.TemporaryDirectory(prefix='logpilot-evaluation-crash-') as scratch:
            path = str(Path(scratch) / 'metrics.duckdb')
            process = subprocess.Popen([sys.executable, '-B', __file__, 'child', path, boundary],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            try:
                if boundary == 'locked':
                    import select
                    assert select.select([process.stdout], [], [], 15)[0], 'child did not become ready'
                    assert process.stdout.readline().strip() == 'READY'
                    try:
                        with evaluation_owner(path):
                            raise AssertionError('live owner was replaced')
                    except RuntimeError:
                        pass
                    process.kill()
                code = process.wait(timeout=15)
                assert code == (-9 if boundary == 'locked' else 78), code
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                process.stdin.close()
                process.stdout.close()
            store = EvaluationStore(path)
            with evaluation_owner(path):
                assert store.interrupt_running() == 1
                assert store.interrupt_running() == 0
            summary = store.summary()
            assert summary['history'][0]['status'] == 'interrupted'
            assert summary['total_cases_24h'] == 2
            assert summary['case_counts_24h']['passed'] == passes
            assert summary['case_counts_24h']['error'] == 2 - passes
            assert summary['pass_rate_24h'] == passes * 50
            print(f'PASS: {boundary}, preserved {passes} completed cases, no pending cases')
    print('PASS: all four evaluator crash/lock boundaries and repeated recovery')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'child':
        child(sys.argv[2], sys.argv[3])
    else:
        main()
