# Isolated test environment — Steps 0.1 and 0.2

Date: 2026-09-10. Starting revision: `12265199f4844ab8e9b5b52cb84c1b33092bf58d`.

This is an expanding baseline for the [enterprise roadmap](enterprise_roadmap.md). Step 0.1 established storage isolation; Step 0.2 now adds HTTP and MCP handler contracts protecting the first Step 1.1 repairs. It is not the full feature suite and is not an end-to-end or enterprise-readiness certification.

## Current checkpoint (2026-09-17)

At `4895c91`, 98 backend tests and six browser contracts passed. [GitHub Actions run 35223139147](https://github.com/Jim-lan/log-pilot/actions/runs/35223139147) passed both jobs, including the abrupt transaction-crash checks in the backend job. The real Chroma/LlamaIndex smoke described below remains an existing-image check, not clean-install CI.

The sections below are an incremental verification history. Counts and statements about stubbed imports or missing coverage describe their checkpoint, not necessarily the latest suite. Current tests exercise real graph, ingestion methods and database paths with scripted external dependencies. They do not establish live-model quality, full-stack deployment readiness or enterprise qualification.

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

The runner selects exactly five files rather than discovering the legacy suite. It disables bytecode writes, creates a fresh temporary working directory before importing tests, clears inherited environment variables (including provider credentials), redirects home/cache paths, enables model-library offline flags and blocks Python network/child-process operations before test collection. Local AF_UNIX socketpair creation is permitted for asyncio thread wakeups used by the in-process HTTP client; network sockets, connect, bind and DNS calls remain blocked. Docker still has `network_mode: none`.

Each storage test gets a separate temporary working directory. Existing relative paths such as `data/target/history.duckdb` therefore resolve into disposable storage. Tests execute real parser, masker and DuckDB connector code. No application data path changes are needed for this initial allowlist. The audit guard rejects Python reads of the project's real data directory and writes outside scratch storage.

No real LLM, embedding model, ingestion worker or RAG store is imported. HTTP tests import the actual API after substituting a scripted graph, then exercise it through FastAPI's in-process client with real temporary DuckDB. MCP tests import real handler code after replacing registration decorators; forwarding uses a mocked HTTP call. They do not verify the MCP transport. Scripted LLM/search doubles in `tests/isolated/fakes.py` remain available for later full graph tests. Synthetic fixtures are under `tests/isolated/fixtures/`; the runbook is not embedded or indexed in this phase.

## Scope of the 57 checks

| Area | Checks |
|---|---|
| Existing parser suite | Standard, JSON, syslog, Nginx and unknown-format fallback (5) |
| Real temporary persistence | Fresh log/history files; parse-mask-insert-query results; history separation at connector level; alert dismissal (4) |
| Safety guards | Reject sockets, child processes, project writes and project-data reads (4) |
| Reusable external doubles | Scripted responses, errors, call tracking and unexpected-call rejection (1) |
| HTTP contracts | First/follow-up queries, history reload, ten-message context limit, RAG response evidence, dictionary/object tool metadata, graph errors, request validation, health, fallback evidence/metadata, deadlines and capacity/budget errors (13) |
| MCP handlers | Real query, recent logs, schema, query errors, and mocked forwarding/timeout (5) |
| Real graph | Happy paths, bounded repair, strict verdicts, search policy/outage, budget propagation and sticky provider failure (14) |
| Budgets and provider adapters | Fake-clock limits/cancellation/context separation plus actual SDK mocked transport and search lifecycle (11) |

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

### Request-budget increment — 2026-09-11

Previous 41-check changes are locally checkpointed at `3963756`. The new `test_budgets.py` expands the allowlist to five files. Tests use the real OpenAI SDK 2.30.0 with HTTPX MockTransport, not live network calls; model registry/token-counting setup and search-client lifecycle use controlled substitutes. The original SDK error-string paths are replaced with typed failures, including the legacy configuration route.

Before implementation, the new HTTP deadline regression failed (returned late success) and five budget-contract tests failed to import the not-yet-implemented module. Final verification: **57 passed, zero failures/errors/skips**, locally with Python 3.9.6 and in Docker with Python 3.11.16. Both Compose configuration checks and `git diff --check` passed. Temporary storage cleanup completed. The strengthened timeout test confirms an occupied worker slot is retained until its operation returns, then checks that the delayed graph answer was not saved.

[Request-budget design](request_budgets.md) records defaults, typed error codes, cancellation/persistence limits and standalone-script scope. Step 1.2 is implemented for the `/query` boundary; live provider performance, load/soak testing, atomic history writes and deployment-wide quotas are not established by this isolated suite. Existing application data and running services were not changed. The query-budget changes remain uncommitted after the local checkpoint.


## Step 1.3 evidence (2026-09-13)

Before repairs, all four new browser tests failed and privacy tests exposed nested masking plus the missing outbound policy. After repairs:

```text
Local Python: Result: {"tests": 61, "failures": 0, "errors": 0, "skipped": 0}
Docker Python: Ran 61 tests; OK
Chrome browser: tests 4; pass 4; fail 0
```

Backend adapter contracts inspect actual OpenAI SDK request bodies via MockTransport and the mocked search client's query to verify redaction before dispatch. They also retain timeout and call-budget checks. Browser contracts exercise real frontend files with synthetic history, model output, references, alerts and HTTP errors; every HTTP request is intercepted locally. No application database or live model is used.

Reproduce browser checks with Node.js 22 or newer and installed Chrome:

```sh
npm ci --prefix tests/frontend --ignore-scripts --no-audit --no-fund
npm test --prefix tests/frontend
```

The default browser path is macOS Google Chrome. On other systems set `LOGPILOT_CHROME_PATH` to an installed Chrome/Chromium executable. Dependency installation needs network access; tests need permission to launch the browser. These tests are separate from the Python-only Docker harness. Full deployment, ingestion, live-model quality, authentication and load coverage remain outstanding.


## Evaluation integrity checkpoint (2026-09-14)

The backend suite expanded to 70 tests: versioned storage, case-weighted failure totals, real UTC time windows, measured latency, unfinished runs, stateless history protection, runner evidence extraction and evaluation API validation. Local Python and network-disabled Docker both report `tests: 70, failures: 0, errors: 0, skipped: 0`. Five Chrome tests pass, including missing metrics displayed as Unavailable.

A disposable existing Nginx image served the current `rendering.js` through HTTP with source mounted read-only, no application data mounts and networking disabled. An initial attempt dropping all Linux capabilities failed to start Nginx; rerunning with the image's standard capabilities succeeded. This is a frontend serving smoke test, not a full-stack or live-model deployment check. The container was removed automatically.

An indexed `UPDATE ... RETURNING` in DuckDB 1.1.3 failed during new storage tests; the implementation now checks and updates inside a transaction without RETURNING, retaining duplicate-write rejection. No production storage was touched.


## Quality corpus and CI (2026-09-14)

The backend suite now contains 73 tests. `test_versioned_quality_fixtures_execute_real_graph_and_database` covers six versioned synthetic SQL cases in real LangGraph/DuckDB, with scripted SQL generation. Additional contracts verify duplicate-preserving row comparison and request-local template/model provenance. These are application correctness tests, not live-model accuracy measurements.

`.github/workflows/isolated-regressions.yml` runs on pull requests, main/codex branch pushes and manual dispatch. Backend tests use the existing network-disabled Docker profile. Browser tests use pinned npm dependencies and Playwright Chromium with every application request fulfilled from synthetic fixtures. Action implementations are pinned to verified commit SHAs and receive read-only contents permission; checkout credentials are not persisted. Dependency/image/browser installation requires network, while the test execution boundaries remain isolated. Remote workflow success must be confirmed from its actual run, not inferred from this configuration.

GitHub Actions verification: [run 34857485746](https://github.com/Jim-lan/log-pilot/actions/runs/34857485746) completed successfully for commit `8f3f8b3dd58a53d673b1c9cf90a2f9e4b40cd892`. Both the Ubuntu Docker backend job and Playwright Chromium browser job passed. This confirms clean remote installation and execution for that revision; later code changes require their own run.


## Retrieval attribution checkpoint (2026-09-14)

76 backend contracts pass locally and in the isolated Docker profile. Added checks cover retrieved artifact identity, a correctly cited answer, deterministic rejection of fabricated citation IDs without relying on the model judge, and independent retrieval/citation/answer failures. Six browser contracts include inert rendering of hostile source titles and readable IDs/hashes. Synthetic KB nodes and scripted LLM output are used; no claim of live retrieval/model quality follows from these tests.


## SQL policy checkpoint (2026-09-15)

84 backend tests pass locally and in the rebuilt network-disabled Docker image. New policy tests reject external readers, multiple statements, hidden/unknown tables and columns, extension/configuration commands and CTE scope confusion. Real DuckDB verifies row limits, engine-level external-read denial even when parsing is bypassed in a test, expensive-query interruption and post-cancellation reuse. MCP and graph tests verify the shared execution boundary and preserve typed request deadline failures. The pinned parser dependency is `sqlglot==26.33.0`.

The preceding citation revision `6840e40817a6842e0aad4342d6c6900a71de921d` also passed [GitHub Actions run 34858072080](https://github.com/Jim-lan/log-pilot/actions/runs/34858072080). No application containers or data were changed by these tests. See [SQL policy scope](sql_execution_policy.md); process isolation, response byte bounds, tenant permissions and concurrent storage ownership are not established by these checks.


## File acknowledgement checkpoint (2026-09-15)

92 tests pass locally and in the isolated Docker profile. Real ingestion worker methods, DuckDB and SQLite are exercised with synthetic files and stubbed watcher/vector/model dependencies. Eight additional contracts cover successful acknowledgement, database/vector failure, quarantine, duplicate completed-file handling, move collision recovery, interrupted claims, empty runbook discovery and changed inputs. This verifies truthful acknowledgement and safe refusal of incomplete replay; it does not establish idempotent partial replay or real Chroma recovery.

The preceding SQL-policy revision `6cbdfa3d6978f10dd21780f2631c0817f856aeed` passed [GitHub Actions run 34969976591](https://github.com/Jim-lan/log-pilot/actions/runs/34969976591). Application data and running services remain untouched.


## Transactional log replay checkpoint (2026-09-17)

98 tests pass locally and in the isolated Docker profile. New contracts cover atomic rollback of rows/event keys, duplicate-safe vector-outage replay, failure between vector upsert and acknowledgement, refusal of legacy/unknown replay inputs, and distinct physical-line identities for duplicate text. Committed records are skipped before parsing/mining during replay.

A separate process-crash test exits abruptly immediately before and after DuckDB COMMIT, then reopens the database and replays twice. Both cases retain exactly one row, one event key and one pending indexing task. It is now part of backend CI:

```sh
docker compose -f compose.test.yml run --rm --no-deps --entrypoint python baseline -B /workspace/tests/integration/ingestion_crash_smoke.py
```

Real Chroma/LlamaIndex smoke test `tests/integration/vector_upsert_smoke.py` passed in the existing ingestion image `sha256:d30487b2f8897731e553e64590e4c9fd1a045791360c8a4fafb2b8cbc487af29`, with synthetic embeddings, a temporary collection and networking disabled. Repeated writes preserved one vector ID; updating its text remained retrievable through the existing LlamaIndex Chroma adapter. This additional smoke is not yet in clean-install CI and does not validate embedding/model quality. No application database was mounted.

The preceding acknowledgement revision `231f25894ac014756fbafc03349169613fd978a3` passed [GitHub Actions run 34983957973](https://github.com/Jim-lan/log-pilot/actions/runs/34983957973). The replay revision subsequently passed run 35223139147, linked in the current checkpoint above. Markdown recovery, legacy vector reconciliation, queue bounds and multi-writer operation remain unproven.

## R01: clean vector integration environment (2026-09-23)

The standalone test Compose profile now includes `vector`, built separately from application images. It pins the Python base digest and vector adapter dependency versions. It mounts only shared code and integration tests read-only, runs as a non-root user without network/capabilities, and keeps its synthetic collection in temporary storage. No model downloads or application data are needed at test runtime.

```sh
docker compose -f compose.test.yml build vector
docker compose -f compose.test.yml run --rm --no-deps vector
```

A child process writes, repeats and updates a stable node, verifies LlamaIndex retrieval, then exits without Python cleanup. Two fresh child processes reopen the persistent collection and replay the operations, asserting that one updated node survives. This tests acknowledged vector persistence and replay across process exit; it does not simulate disk/power loss or prove the complete ingestion transaction protocol. GitHub Actions has a separate vector job so a fresh runner exercises dependency installation independently of a cached application image.

Local R01 verification passed with the complete dependency lock: clean build and `pip check`, all three real-vector child-process passes and final restart/replay assertion. The 98 backend contracts also pass locally and in Docker after the separately committed deterministic-clock repair (`943634c`). Remote vector-job verification is pending the R01 push.
