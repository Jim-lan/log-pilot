# Isolated test environment — Step 0.1

Date: 2026-09-10. Starting revision: `12265199f4844ab8e9b5b52cb84c1b33092bf58d`.

This is a deliberately small baseline for the [enterprise roadmap](enterprise_roadmap.md). It establishes a safe place to test before application changes. It is not the full feature suite from Step 0.2 and is not an end-to-end or enterprise-readiness certification.

## Run locally

From the project folder, create a separate environment once:

```sh
python3 -m venv .venv-test
.venv-test/bin/python -m pip install --no-cache-dir -r tests/isolated/requirements.txt
```

Then run:

```sh
.venv-test/bin/python -B scripts/run_isolated_tests.py
```

The first install needs network access. The suite itself is offline. Do not activate or alter the existing `venv`; `.venv-test/` is ignored by Git. Only DuckDB 1.1.3 is required; the test runner uses Python's standard library. Missing dependencies cause a failure rather than a skipped storage test. Run the script as a separate process because its environment cleanup and audit hooks intentionally last until process exit.

## Run with Docker isolation

```sh
docker compose -f compose.test.yml build baseline
docker compose -f compose.test.yml run --rm --no-deps baseline
```

This is a standalone Compose file. Do not combine it with `docker-compose.yml`. Build downloads the pinned Python base and DuckDB dependency; runtime has no network. The build context contains only the test Dockerfile and requirements. The test service uses:

- A read-only root filesystem and read-only mounts of explicitly selected source/test paths.
- No project `data/`, application configuration, credentials, home folder or Docker socket mount.
- No published ports, persistent data volumes, application services or model servers.
- A non-root user, dropped capabilities, no privilege escalation, bounded memory/CPU/processes.
- Temporary in-memory `/tmp` storage removed with the one-off container.

The Docker image remains cached after a run; `--rm` removes the test container. Do not run blanket prune or application teardown commands to clean test resources.

Docker provides the OS-level boundary. Local Python audit hooks only guard accidental Python filesystem/network/subprocess use; native extensions can bypass them. Run any expanded or unreviewed suite in Docker, not on the assumption that the Python hooks form a complete sandbox.

## How data and dependencies are isolated

The runner selects exactly two files rather than discovering the legacy suite. It disables bytecode writes, creates a fresh temporary working directory before importing tests, clears inherited environment variables (including provider credentials), redirects home/cache paths, enables model-library offline flags and blocks Python socket/child-process operations before test collection.

Each storage test gets a separate temporary working directory. Existing relative paths such as `data/target/history.duckdb` therefore resolve into disposable storage. Tests execute real parser, masker and DuckDB connector code. No application data path changes are needed for this initial allowlist. The audit guard rejects Python reads of the project's real data directory and writes outside scratch storage.

No LLM, embedding model, API, ingestion worker or RAG store is imported by the baseline. Scripted LLM/search doubles are provided in `tests/isolated/fakes.py`; an unplanned extra LLM call raises an error. They are tested as reusable boundaries but are not yet wired into full agent tests. Synthetic logs and a synthetic runbook live under `tests/isolated/fixtures/`; the runbook is not embedded or indexed in this phase.

## Scope of the 14 checks

| Area | Checks |
|---|---|
| Existing parser suite | Standard, JSON, syslog, Nginx and unknown-format fallback (5) |
| Real temporary persistence | Fresh log/history files; parse-mask-insert-query results; history separation at connector level; alert dismissal (4) |
| Safety guards | Reject sockets, child processes, project writes and project-data reads (4) |
| Reusable external doubles | Scripted responses, errors, call tracking and unexpected-call rejection (1) |

Connector-level session separation does not establish API authorization: the current API still uses a shared default session. Passing these checks does not mean conversation, RAG, MCP, ingestion recovery or evaluation defects are fixed.

## Inventory: why broad test discovery is not enabled yet

| Existing area | Side effect or mismatch | Next action |
|---|---|---|
| `tests/test_alert_persistence.py`, `tests/verify_sentry.py` | Default connector can initialize/write project databases | Convert to assertive tests using temporary data; 0.2 |
| `tests/test_drain3_integration.py` | Deletes a state file and writes under relative `data/`; some failures only print | Isolate paths and assert results; 0.2 |
| Knowledge-store/agent/API imports | Global HuggingFace embedding initialization can load/download a model before test-level mocks | Stub dependency boundary before import or introduce lazy initialization in a separate tested change; 0.2 |
| Evaluation modules/scripts | Fixed `/app/data` paths, model initialization and live HTTP calls | Dedicated isolated service fixtures; 2.1 |
| Orchestrator tests and mocked E2E | Some patches name removed `sql_tool`/`get_db_client` symbols; health assertion is outdated | Repair the harness without concealing product failures; 0.2 |
| Legacy verification/reset scripts | Some directly write/delete data or invoke live providers | Excluded; individually review before execution |

No tests are silently marked passing or expected-failing to work around these problems. Exclusion is explicit: only the listed 14 checks run. Full-suite collection is a future deliverable.

## Known application failures still open

| Finding from September review | Evidence/status | Roadmap owner |
|---|---|---|
| Dictionary history trace can produce HTTP 500 | Earlier isolated function reproduction; not fixed or covered by this small suite | 1.1 |
| MCP accesses removed `db.conn` | Source-confirmed; not fixed | 1.1 |
| Rejected context/answers do not advance retries; fallback destination missing | Earlier isolated reproduction/source check; not fixed | 1.2 |
| Shared API session, unsafe HTML/SQL, uncontrolled egress | Source findings; not fixed | 1.3 / 3 |
| Nested-list dictionary PII remains unmasked | Earlier isolated reproduction; not fixed | 3.3 |
| Evaluation schema/context/latency mismatches | Source findings; not fixed | 2.1 |
| Ingestion acknowledgment/replay and cross-process storage gaps | Source findings; recovery/load tests still needed | 4 / 5 |

## Baseline evidence

The existing application virtual environment has Python 3.9.6 and DuckDB 1.4.2, whereas application service requirements pin DuckDB 1.1.3. An exploratory run in that existing environment passed all 14 checks; it is not the canonical baseline. The separate test environment pins 1.1.3 without modifying application dependencies. The Docker test runtime uses Python 3.11 with a pinned base digest; this is a test-only runtime, not an application Python upgrade or complete production parity.

The runner prints Python/DuckDB versions, its exact file allowlist, per-test results, counts and temporary-storage cleanup. See the execution record below for the validated environments. Full application dependency locking and deployed-runtime parity remain later work.

### Execution record

Validated on 2026-09-10:

| Environment | Python | DuckDB | Result |
|---|---|---|---|
| Dedicated `.venv-test` | 3.9.6 | 1.1.3 | 14 passed, 0 failures, 0 errors, 0 skipped |
| Standalone Docker baseline | 3.11.16 | 1.1.3 | 14 passed, 0 failures, 0 errors, 0 skipped |

Both reported `Scratch storage removed.` The Docker container exited successfully and was removed by `--rm`. No existing application containers were running at the start. No application service was started or application code changed for these runs.

Step 0.1 is complete for the explicit baseline scope. Next: Step 0.2, expand deterministic feature contracts and repair legacy test setup; retain the known failures above until separately reproduced and fixed.
