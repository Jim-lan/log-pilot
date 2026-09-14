# Evaluation integrity contract v1

## Decision

The previous runner skipped request failures, looked for context in the wrong response field, discarded measured latency and wrote `eval_runs_micro` while the dashboard read `eval_runs`. Those numbers cannot establish quality. New additive tables `evaluation_runs_v1` and `evaluation_cases_v1` are the common runner/dashboard contract. Existing tables and data remain untouched and are not relabeled as trustworthy results.

A run persists its complete case roster before background execution. Cases start pending and become passed, failed, error or unscored. Every planned case remains in the denominator. A normal finish converts unprocessed cases to errors; a process crash leaves an explicitly running run and pending cases for operator investigation. There is no durable job resumption yet. Writes use short connections and transactions; cross-process DuckDB ownership remains a Phase 5 issue.

The runner reads top-level `context`, `sql`, `sql_result`, `answer` and response metadata. Latency is measured by a monotonic clock around each request, including failed requests. A missing latency remains null. Stored evidence is evaluation data and may contain sensitive material; use synthetic datasets only until the complete data policy is implemented.

## Scoring and provenance

Deterministic checks require an `expected_sql_result` or `expected_answer`. They compare actual returned values exactly; SQL text or keyword matches alone cannot pass a case. Optional expected intent is checked in addition. This is a first exact-result contract, not normalization of arbitrary SQL row order or semantic answer equivalence. Legacy datasets without these expectations are unscored and cannot inflate pass rates. Optional `/evaluate` Ragas judge scores are separate from deterministic pass rates and initialize only on demand.

Each run records the dataset SHA-256, limit, contract version and scorer. Model identity and prompt version are explicitly unrecorded until the API supplies trusted provenance. Versioned synthetic fixture datasets, multi-turn evaluation sessions, retrieval/citation checks and repeated live-model measurements are still Phase 2.2 work. Simulated shadow output is disabled: copying a primary answer does not measure a second model.

## API and display

`POST /query` accepts `persist_history: false` for stateless evaluation: neither read ordinary history nor append the interaction. This is an additive local-development contract, not identity or authorization. It does not isolate logs or vectors and cannot support multi-turn evaluation yet.

`POST /evaluate/batch` reads only `EVALUATION_DATASET_PATH` (default `/app/tests/evaluation/golden_dataset.json`). A client-supplied `dataset_path` must match that configured path; arbitrary paths are rejected. Positive limits are bounded at 1000. `METRICS_DB_PATH` configures the storage location for both services; their defaults resolve to the same shared application data mount.

`GET /metrics` returns `schema_version: 1`, availability status, case-weighted `pass_rate_24h`, measured `avg_latency_24h`, all-time `total_runs`, and the latest ten runs with durable status. The window uses UTC run timestamps within the preceding 24 hours; pending/error/unscored cases do not count as passes. Missing databases, old-only schemas and unavailable storage return null metrics rather than invented zero scores. The UI renders null as Unavailable. Reads never create tables.

## Experiment and rollout

Disposable DuckDB tests cover a passing case, incorrect output, failed request, unfinished run, old results outside the time window, actual evidence and request latency. API tests prove ordinary history is unchanged and the dashboard reads the same schema. Browser tests protect unavailable values and existing rendering behavior.

No existing data migration or application container restart is performed by these repairs. Try the new evaluator with a synthetic configured dataset before normal use. Rollback may ignore the additive v1 tables; retain them for reconciliation rather than deleting results. These tests do not establish live-model quality, concurrent storage safety or completion of Phase 2.
