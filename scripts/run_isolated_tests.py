#!/usr/bin/env python3
"""Run an explicit offline baseline; never discover the legacy suite implicitly."""
import importlib.util
import json
import os
import socket
from pathlib import Path
import sys
import tempfile
import unittest
from importlib.metadata import version

ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = ("tests/test_parser_formats.py", "tests/isolated/test_environment.py",
              "tests/isolated/test_api_mcp.py", "tests/isolated/test_graph.py",
              "tests/isolated/test_budgets.py", "tests/isolated/test_privacy.py", "tests/isolated/test_evaluation.py", "tests/isolated/test_sql_policy.py", "tests/isolated/test_ingestion.py", "tests/isolated/test_document_identity.py", "tests/isolated/test_file_intake.py")


def install_guards(scratch):
    """Defense against accidental Python I/O, not an OS/native-code sandbox."""
    scratch = scratch.resolve()
    protected = (ROOT / "data").resolve()

    def check(path, write=False):
        if path is None or isinstance(path, int):
            return
        path = Path(os.fsdecode(path)).resolve()
        if path == protected or protected in path.parents:
            raise PermissionError("Isolated tests cannot access project data")
        if write and path != scratch and scratch not in path.parents:
            raise PermissionError("Isolated tests may write only inside scratch storage")

    def audit(event, args):
        # asyncio uses a local socketpair for thread wakeups. Permit creation of
        # AF_UNIX sockets only; all connect/bind/DNS calls remain prohibited.
        if event == "socket.__new__" and args[1] == socket.AF_UNIX:
            return
        if event.startswith("socket.") or event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.fork"):
            raise PermissionError("Network and child processes are disabled in isolated tests")
        if event == "open":
            path, mode, flags = args
            write = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            check(path, write)
        elif event in ("os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.truncate", "os.utime"):
            check(args[0], True)
        elif event in ("os.rename", "os.link", "os.symlink"):
            check(args[0], True)
            check(args[1], True)
        elif event in ("os.listdir", "os.scandir"):
            check(args[0])

    sys.addaudithook(audit)


def main():
    sys.dont_write_bytecode = True
    # No third-party pytest plugin discovery, application startup or model imports.
    sys.path.insert(0, str(ROOT))
    baseline = {"python": sys.version.split()[0],
                "dependencies": {name: version(name) for name in ("duckdb", "fastapi", "pydantic", "httpx", "requests")},
                "suite": list(TEST_FILES)}
    print("Runtime: " + json.dumps(baseline), flush=True)
    with tempfile.TemporaryDirectory(prefix="logpilot-tests-") as directory:
        scratch = Path(directory).resolve()
        os.chdir(scratch)
        os.environ.clear()  # Do not forward developer API keys to test code.
        os.environ.update({
            "HOME": str(scratch), "TMPDIR": str(scratch),
            "XDG_CACHE_HOME": str(scratch / "cache"), "HF_HOME": str(scratch / "hf"),
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "PYTHONDONTWRITEBYTECODE": "1", "TOKENIZERS_PARALLELISM": "false",
            "LOGPILOT_TEST_SCRATCH": str(scratch),
        })
        install_guards(scratch)
        suite = unittest.TestSuite()
        for index, relative in enumerate(TEST_FILES):
            spec = importlib.util.spec_from_file_location("baseline_" + str(index), ROOT / relative)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        print("Result: " + json.dumps({"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)}), flush=True)
        os.chdir(ROOT)
    print("Scratch storage removed.", flush=True)
    return 0 if result.wasSuccessful() and result.testsRun and not result.skipped else 1


if __name__ == "__main__":
    sys.exit(main())
