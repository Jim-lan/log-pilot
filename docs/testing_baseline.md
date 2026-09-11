# Isolated test environment — Steps 0.1 and 0.2

Date: 2026-09-10. Starting revision: `12265199f4844ab8e9b5b52cb84c1b33092bf58d`.

This is an expanding baseline for the [enterprise roadmap](enterprise_roadmap.md). Step 0.1 established storage isolation; Step 0.2 now adds HTTP and MCP handler contracts protecting the first Step 1.1 repairs. It is not the full feature suite and is not an end-to-end or enterprise-readiness certification.

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

The first install needs network access. The suite itself is offline. Do not activate or alter the existing `venv`; `.venv-test/` is ignored by Git. DuckDB, FastAPI, Pydantic, HTTPX and Requests direct dependencies are pinned in the test requirements; the runner uses standard-library unittest. Re-run the install command when those requirements change. Missing dependencies cause failure rather than skipped tests. Run the script as a separate process because its environment cleanup and audit hooks intentionally last until process exit.

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

The runner selects exactly four files rather than discovering the legacy suite. It disables bytecode writes, creates a fresh temporary working directory before importing tests, clears inherited environment variables (including provider credentials), redirects home/cache paths, enables model-library offline flags and blocks Python network/child-process operations before test collection. Local AF_UNIX socketpair creation is permitted for asyncio thread wakeups used by the in-process HTTP client; network sockets, connect, bind and DNS calls remain blocked. Docker still has `network_mode: none`.

Each storage test gets a separate temporary working directory. Existing relative paths such as `data/target/history.duckdb` therefore resolve into disposable storage. Tests execute real parser, masker and DuckDB connector code. No application data path changes are needed for this initial allowlist. The audit guard rejects Python reads of the project's real data directory and writes outside scratch storage.

No real LLM, embedding model, ingestion worker or RAG store is imported. HTTP tests import the actual API after substituting a scripted graph, then exercise it through FastAPI's in-process client with real temporary DuckDB. MCP tests import real handler code after replacing registration decorators; forwarding uses a mocked HTTP call. They do not verify the MCP transport. Scripted LLM/search doubles in `tests/isolated/fakes.py` remain available for later full graph tests. Synthetic fixtures are under `tests/isolated/fixtures/`; the runbook is not embedded or indexed in this phase.

## Scope of the 41 checks

| Area | Checks |
|---|---|
| Existing parser suite | Standard, JSON, syslog, Nginx and unknown-format fallback (5) |
| Real temporary persistence | Fresh log/history files; parse-mask-insert-query results; history separation at connector level; alert dismissal (4) |
| Safety guards | Reject sockets, child processes, project writes and project-data reads (4) |
| Reusable external doubles | Scripted responses, errors, call tracking and unexpected-call rejection (1) |
| HTTP contracts | First/follow-up queries, history reload, ten-message context limit, RAG response evidence, dictionary/object tool metadata, graph errors, request validation, health and web-fallback evidence/metadata (10) |
| MCP handlers | Real query, recent logs, schema, query errors, and mocked forwarding/timeout (5) |

Connector-level session separation does not establish API authorization: the current API still uses a shared default session. Passing these checks verifies the repaired history serialization and MCP connector calls, not full RAG execution, MCP transport, ingestion recovery or evaluation correctness.

## Inventory: why broad test discovery is not enabled yet

| Existing area | Side effect or mismatch | Next action |
|---|---|---|
| `tests/test_alert_persistence.py`, `tests/verify_sentry.py` | Default connector can initialize/write project databases | Convert to assertive tests using temporary data; 0.2 |
| `tests/test_drain3_integration.py` | Deletes a state file and writes under relative `data/`; some failures only print | Isolate paths and assert results; 0.2 |
| Knowledge-store/agent/API imports | Global HuggingFace embedding initialization can load/download a model before test-level mocks | Stub dependency boundary before import or introduce lazy initialization in a separate tested change; 0.2 |
| Evaluation modules/scripts | Fixed `/app/data` paths, model initialization and live HTTP calls | Dedicated isolated service fixtures; 2.1 |
| Orchestrator tests and mocked E2E | Some patches name removed `sql_tool`/`get_db_client` symbols; health assertion is outdated | Repair the harness without concealing product failures; 0.2 |
| Legacy verification/reset scripts | Some directly write/delete data or invoke live providers | Excluded; individually review before execution |

No tests are silently marked passing or expected-failing to work around these problems. Exclusion is explicit: only the allowlisted checks run. Full-suite collection and migration of the stale legacy test modules remain future deliverables; the new contracts do not import their global mocks.

## Application findings and current status

| Finding from September review | Evidence/status | Roadmap owner |
|---|---|---|
| Dictionary history trace can produce HTTP 500 | Reproduced through HTTP; repaired and protected by follow-up/history regressions | 1.1 core repair done |
| MCP accesses removed `db.conn` | Reproduced against real DuckDB; all three handlers repaired | 1.1 core repair done |
| Rejected context/answers do not advance retries; fallback destination missing | Reproduced with real graph execution; independent counters, strict verdicts and fallback repaired | 1.2 budgets still pending |
| Shared API session, unsafe HTML/SQL, uncontrolled egress | Source findings; not fixed | 1.3 / 3 |
| Nested-list dictionary PII remains unmasked | Earlier isolated reproduction; not fixed | 3.3 |
| Evaluation schema/context/latency mismatches | Source findings; not fixed | 2.1 |
| Ingestion acknowledgment/replay and cross-process storage gaps | Source findings; recovery/load tests still needed | 4 / 5 |

## Baseline evidence

The existing application virtual environment has Python 3.9.6 and DuckDB 1.4.2, whereas application service requirements pin DuckDB 1.1.3. An exploratory run in that existing environment passed all 14 checks; it is not the canonical baseline. The separate test environment pins 1.1.3 without modifying application dependencies. The Docker test runtime uses Python 3.11 with a pinned base digest; this is a test-only runtime, not an application Python upgrade or complete production parity.

The runner prints Python/DuckDB versions, its exact file allowlist, per-test results, counts and temporary-storage cleanup. See the execution record below for the validated environments. Full application dependency locking and deployed-runtime parity remain later work.

### Original Step 0.1 execution record

Validated on 2026-09-10:

| Environment | Python | DuckDB | Result |
|---|---|---|---|
| Dedicated `.venv-test` | 3.9.6 | 1.1.3 | 14 passed, 0 failures, 0 errors, 0 skipped |
| Standalone Docker baseline | 3.11.16 | 1.1.3 | 14 passed, 0 failures, 0 errors, 0 skipped |

Both reported `Scratch storage removed.` The Docker container exited successfully and was removed by `--rm`. No existing application containers were running at the start. No application service was started or application code changed for these runs.

Step 0.1 is complete for the explicit baseline scope. Next: Step 0.2, expand deterministic feature contracts and repair legacy test setup; retain the known failures above until separately reproduced and fixed.

### Step 0.2 / 1.1 increment

Starting revision: `efad7fc05080702982708bbfea8d1745c57d30e2`. Branch: `codex/baseline-api-mcp-regressions`.

Before the product fix: 26 checks executed, 22 passed and four failed (second-turn HTTP 500 and three MCP connector failures). After the fix: those 26 passed locally and in Docker. Two additional compatibility checks cover dictionary tool metadata and the ten-message context limit.

Final verification on 2026-09-10: **28 passed, 0 failures, 0 errors, 0 skipped**, both locally (Python 3.9.6) and in Docker (Python 3.11.16). Both use DuckDB 1.1.3, FastAPI 0.115.6, Pydantic 2.10.4, HTTPX 0.28.1 and Requests 2.32.3. Scratch cleanup completed in both runs. Application data was not mounted in Docker.

The system Python 3.9 local run emits an urllib3 warning about its LibreSSL build. These tests make no outbound HTTPS requests; use the isolated Docker runtime for canonical verification. This does not validate live-provider TLS from that local Python installation.

Learning: substituting only external boundaries while using real storage exposed bugs that broad MagicMock connectors had hidden. HTTP response contracts and database behavior are verified independently of model quality. The repair is additive, has no schema migration and can be reverted as a code change; existing session isolation/security limitations remain open. Full execution-event tracing, CI and legacy harness cleanup are still pending. Real graph tests are added in the next increment below.

### Graph increment — 2026-09-11

The allowlist now includes `tests/isolated/test_graph.py`: real LangGraph 0.6.11, node functions, Jinja templates and temporary DuckDB, with only LLM/search/vector-store boundaries substituted. Prompt files are mounted read-only. Jinja2 3.1.6 and PyYAML 6.0.2 are added to test requirements. Direct dependency pins are not a complete transitive lockfile.

Twelve graph checks cover SQL and runbook happy paths, rejected/empty context, answer exhaustion, malformed/non-boolean verdicts, independent SQL/answer retries, SQL exhaustion, disabled search, and raised/string-reported search outages. One additional HTTP check verifies fallback evidence and retry metadata. No live models, real embeddings or external search are exercised.

Before graph repair: 36 checks ran with four assertion failures and two recursion-limit errors. After the repair and additional coverage, the final suite contains 41 checks. Independent counters bound SQL repairs to three and context/answer retries to two each. Failed answer validation abstains; web search requires explicit operator opt-in. The main Compose file forwards that flag but no application container was started or restarted.

Final verification: **41 passed, zero failures/errors/skips** locally (Python 3.9.6) and in Docker (Python 3.11.16), both using DuckDB 1.1.3. Scratch cleanup completed; `git diff --check` and both Compose configuration checks passed. The application behavior is changed on the working branch, not deployed. Earlier chat/MCP repairs remain in this same uncommitted increment.

Learning: verify termination and failure semantics on the real state machine, not just isolated node mocks. A recursion-step limit and per-stage retry counts do not establish a wall-clock deadline; global request deadlines, provider timeouts/call budgets and comprehensive typed LLM failure handling remain the next increment. Full graph execution traces, UI/ingestion coverage and CI also remain open.
