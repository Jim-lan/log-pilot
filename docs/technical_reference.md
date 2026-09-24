# LogPilot technical reference

Baseline: `4895c91` (2026-09-17). See [system design](system_design.md) for capability status and future changes, and [run guide](../HOW_TO_RUN.md) for commands.

## Code map

| Path | Responsibility |
|---|---|
| `services/pilot_orchestrator/src/api.py` | Query admission, API contracts, history, alerts and metrics |
| `services/pilot_orchestrator/src/` | LangGraph routing, state and bounded repair |
| `services/ingestion-worker/src/main.py` | File worker and explicit replay CLI |
| `services/sentry/src/main.py` | Error-rate alert polling |
| `services/mcp_server/src/main.py` | MCP tools and resources |
| `services/evaluation_service/src/main.py` | Evaluation HTTP service |
| `services/frontend/src/` | Static browser application |
| `shared/db/duckdb_client.py` | Analytics persistence and restricted execution |
| `shared/sql_policy.py` | SQL parser/schema/function policy |
| `shared/vector_upsert.py` | Stable-ID Chroma upsert through compatible LlamaIndex nodes |
| `shared/evaluation.py`, `shared/evaluation_runner.py` | Versioned evaluation storage/scoring and batch execution |
| `shared/privacy.py`, `shared/utils/pii_masker.py` | Provider-boundary redaction and ingestion masking |
| `config/llm_config.yaml`, `prompts/` | Model routing configuration and prompt templates |

Main runtime uses Python/FastAPI, LangGraph, LlamaIndex, DuckDB, SQLite, embedded Chroma, Drain3, Ollama and vanilla JavaScript/Nginx. Ragas is an optional supplementary evaluation judge. Auxiliary/legacy directories are not evidence of active Compose services.

## Persistent data contracts

Paths below are relative to repository root, mounted under `/app` in application containers.

| Path | Contents and contract |
|---|---|
| `data/target/logs.duckdb` | `logs`, optional loaded `system_catalog`, `ingestion_events_v1`, `ingestion_outbox_v1` |
| `data/target/history.duckdb` | Shared default conversation and alerts; no tenant boundary |
| `data/target/metrics.duckdb` | `evaluation_runs_v1` and `evaluation_cases_v1`; legacy metrics excluded from new summaries |
| `data/target/vector_store` | Embedded Chroma collection `log_pilot_kb` |
| `data/state/ingestion.sqlite3` | File fingerprint/state/protocol plus document versions, raw originals, topic plans and card indexing journal |
| `data/state/ingestion.lock` | Local cooperating worker/replay exclusion |
| `data/state/drain3_state.bin` | Pattern miner state |
| `data/source/landing_zone`, `processed`, `quarantine` | Immutable input, completed input and failed/reviewable input |

`logs` exposes timestamp, severity, service_name, trace_id, body, environment, app_id, department, host, region and context (JSON text). `system_catalog` exposes system_name, department, owner_email and criticality when loaded from `data/system_catalog.csv`. The restricted SQL surface excludes ingestion bookkeeping tables.

Log event IDs are content fingerprint plus physical-line ordinal. Outbox records carry event ID, file ID, payload and completion state. These schemas are additive; do not delete legacy data or rewrite IDs as a routine upgrade. See [recovery details](ingestion_recovery.md).

## Request settings

The main Compose file forwards these orchestrator settings:

| Environment variable | Default |
|---|---:|
| `LOGPILOT_REQUEST_TIMEOUT_SECONDS` | 120 |
| `LOGPILOT_LLM_TIMEOUT_SECONDS` | 30 |
| `LOGPILOT_SEARCH_TIMEOUT_SECONDS` | 10 |
| `LOGPILOT_MAX_LLM_CALLS` | 16 |
| `LOGPILOT_MAX_SEARCH_CALLS` | 1 |
| `LOGPILOT_QUERY_WORKERS` | 4 |
| `LOGPILOT_ALLOW_WEB_SEARCH` | false |

Do not raise limits without measuring capacity. Restricted SQL defaults to 1,000 returned rows, five seconds (capped by remaining request budget), 256 MB engine memory and one engine thread; excess rows produce failure rather than silent truncation. SQL text is limited to 20,000 characters. See [policy](sql_execution_policy.md) for exact scope and internal override caps.

The evaluation service reads `PILOT_API_URL`, `METRICS_DB_PATH` and `EVALUATION_DATASET_PATH`; the default dataset is `/app/tests/evaluation/golden_dataset.json`. Optional judge configuration uses `LLM_BASE_URL` and `EVALUATION_JUDGE_MODEL`. API metrics also read `METRICS_DB_PATH`. A process-supported variable is not automatically forwarded by Compose; configure the relevant service explicitly. There is no documented `LOGS_DB_PATH` environment contract.

## Model configuration

The registry loads `config/llm_config.yaml`. The selected local provider currently names `http://llm-service:11434/v1` and model identifier `gemma4:e4b`; this records configuration, not verified model availability or a hardware recommendation. Main Compose also embeds that pull identifier in its startup command, so model changes must keep both consistent.

For registry routing, `models.fast` or `models.reasoning` overrides `default_model`, then the environment fallback applies. Local endpoint fallback uses `LLM_BASE_URL`; API credentials come from the environment variable named by `api_key_env`. The chat client uses an OpenAI-compatible API; listing a provider in YAML does not establish native protocol compatibility. Registry temperature is 0.1; legacy fallback is 0.2. Verify the selected path before comparing runs.

Request provenance captures template source hashes and requested/returned model identity and provider fingerprint where available. It excludes credentials and rendered prompt content. Provider-reported identity is not independently attested. Simulated shadow output is disabled; `SHADOW_MODEL` is not proof of an active independent comparison.

## Development verification

Use [isolated tests](testing_baseline.md), not application data. The test image pins its dependencies; application images/dependencies are not all pinned. Backend tests exercise real graph/database paths with scripted provider responses. Browser tests use synthetic intercepted responses. These establish selected contracts, not model quality or full deployment readiness.

Current recorded evidence at the baseline is 98 backend tests and six browser contracts, plus transaction crash checks and a separate existing-image vector smoke. Keep historical counts attached to their revisions. The [evaluation contract](evaluation_contract.md) defines how to report new measurements without mixing incompatible scores.

Ingestion admission uses `LOGPILOT_INGEST_QUEUE_SIZE` (default 256, 1–10,000), forwarded by main Compose to `ingestion-worker`. Directory polling bounds pending paths; overflow stays in the landing directory. This is separate from the API query-worker limit.

`LOGPILOT_INGEST_MAX_RETRIES` defaults to 2 (0–5), forwarded to the ingestion worker. It limits automatic retries of recognized journaled transient failures, with interruptible exponential backoff. `scripts/inspect_ingestion.py` provides bounded read-only recovery metadata without model startup. See [retry policy](ingestion_recovery.md).

Legacy recovery planning uses `scripts/reconcile_ingestion_snapshot.py` against an offline copied snapshot. It opens vector storage only on a temporary second copy and produces a bounded, non-destructive report. It has no apply/delete mode; see [ADR 0002](decisions/0002-legacy-reconciliation.md).
