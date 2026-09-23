# Security and deployment boundaries

Baseline: `4895c91`, 2026-09-17. LogPilot remains a local development prototype. This document describes implemented controls and requirements for a future shared pilot; it is not a deployment approval.

## Implemented controls

- Model-generated and MCP analytics SQL share a parser/schema/function allowlist and restricted read-only DuckDB execution. External access and extension auto-loading are disabled; row, time and engine memory limits apply. Read-only mode alone is not the SQL security boundary. See [SQL policy](sql_execution_policy.md).
- Plain browser fields are escaped; model Markdown uses a vendored parser and sanitizer with an allowlist. Source titles, SQL, context and alerts remain inert text. See [rendering design](rendering_and_privacy.md).
- Shared LLM/search boundaries apply best-effort PII and credential redaction. Ingestion masking lives in `shared/utils/pii_masker.py`; markers include `<EMAIL_REDACTED>`, `<IP_REDACTED>`, `<CC_REDACTED>` and `<SSN_REDACTED>`.
- External search defaults off. Main Compose host ports bind to loopback. Request deadlines, logical provider budgets and a bounded active query executor constrain selected resource use.
- Standalone test Compose has no network, no application data mounts, a read-only filesystem, non-root user and temporary scratch storage. Installing test dependencies/images still requires network.

## Current exposure and gaps

Main Compose publishes frontend 3000, API 8000, MCP 8001, evaluation 8002 and Ollama 11434, all on `127.0.0.1`. Loopback binding limits remote reachability but is not authentication. Existing containers require recreation to apply changed Compose bindings; editing configuration does not change a running deployment.

The API has wildcard CORS with credentials enabled. There is no user authentication, workspace/tenant authorization or isolated history. MCP, evaluation, history and alerts require the same future access-control design as queries. Do not expose these ports to a shared network as a substitute for that work.

Redaction is not comprehensive DLP. Raw landing/quarantine/processed files, original Markdown snapshots in the SQLite journal, stored context, debug output, embeddings and backups need an explicit sensitive-data lifecycle. Cloud inference and opt-in search can send content externally; local inference does not make every dependency local (the frontend also uses external Google Fonts). Citation IDs prove membership in retrieved artifacts, not their authenticity or factual support.

The SQL worker is not OS-process isolated. Response byte bounds, connection acquisition bounds, tenant row filtering and complete quotas remain open. Several services share embedded storage; availability under concurrent ownership, lock contention and storage failure is not established. Some legacy endpoints/MCP return exception strings; sanitized query errors are not a system-wide guarantee.

## Application startup versus testing

Main Compose is a demo deployment: startup can pull a model, generate source logs and copy a catalog. It has dependency start ordering rather than comprehensive readiness checks, and runtime artifacts are not fully pinned. It must not be merged with `compose.test.yml`. Use [HOW_TO_RUN](../HOW_TO_RUN.md) and [testing baseline](testing_baseline.md) for the distinct workflows.

No production migration or deployment was performed as part of this documentation update. Do not run reset scripts against existing data as an upgrade procedure.

## Shared pilot acceptance gates

1. Identity, trusted authorization and scoped ownership enforced across SQL, vectors, conversations, alerts, evaluation and MCP; cross-scope denial tests pass.
2. Same-origin or explicit-origin browser deployment, authenticated service exposure, secret handling and redacted diagnostics reviewed.
3. Runtime versions pinned; model preparation and demo data generation separated from normal startup; liveness/readiness and disposable full-stack tests pass.
4. Storage ownership and bounded execution defined; load, failure and recovery tests meet agreed numeric objectives.
5. Retention/deletion and backup procedures cover raw inputs, ledgers, databases, vectors and configuration. Restore and migration rollback preserve required records, including writes after cutover.
6. Restricted pilot audience and incident/rollback runbooks established before shared access.

Detailed dependencies and proposed designs: [system design](system_design.md) and [enterprise roadmap](enterprise_roadmap.md).
