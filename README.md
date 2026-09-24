# LogPilot

LogPilot is a local-first AI observability prototype for asking questions about logs and operational knowledge. It combines natural-language SQL, retrieval, runbook ingestion, conversation history, heuristic alerts and MCP access. The project is being hardened incrementally as an enterprise AI engineering learning project; it is not yet ready for shared enterprise deployment.

## Current capabilities

- Bounded LangGraph orchestration with request deadlines, provider budgets, repair limits and explicit failure/abstention behavior.
- Restricted DuckDB analytics shared by model-generated SQL and MCP, with structured rows for deterministic evaluation.
- Embedded Chroma/LlamaIndex retrieval, artifact IDs/content hashes and rejection of unknown citation IDs.
- Immutable-file ingestion with truthful acknowledgement, quarantine, transactional log event/outbox persistence and duplicate-safe protocol-2 log replay.
- Safely rendered chat/evidence, best-effort provider-boundary redaction and opt-in external search.
- Versioned evaluation contracts, honest failure denominators, separate retrieval/citation scores and request provenance.
- Isolated backend/browser regression tests and GitHub CI.

The frontend uses vanilla JavaScript with Nginx; the backend uses Python/FastAPI, LangGraph, DuckDB, SQLite, Chroma, LlamaIndex and Drain3. Main Compose defines eight services, including Ollama, Sentry, evaluation, MCP and a demo generator. Chroma is embedded storage, not its own Compose server.

## Start here

| Document | Purpose |
|---|---|
| [System design](docs/system_design.md) | Complete implemented feature inventory, new designs, tradeoffs and staged future rollout |
| [Implementation tasks](docs/implementation_tasks.md) | Prioritized remaining fixes, dependencies and completion checks |
| [Architecture](docs/architecture.md) | Current services, query/ingestion flows and storage boundaries |
| [Technical reference](docs/technical_reference.md) | Code map, persisted data and supported configuration |
| [Run guide](HOW_TO_RUN.md) | Safe local checks, isolated tests and explicit demo startup |
| [API reference](docs/api_reference.md) | Query, history, alerts, evaluation and MCP contracts |
| [Security/deployment](docs/security_deployment.md) | Existing safeguards and shared-pilot gates |
| [Enterprise roadmap](docs/enterprise_roadmap.md) | Detailed phased implementation and learning plan |
| [Feature coverage](docs/feature_contract_coverage.md) | Protected contracts, legacy test disposition and remaining verification gates |
| [Verification history](docs/testing_baseline.md) | Reproducible commands and revision-specific evidence |

Focused designs: [request budgets](docs/request_budgets.md), [SQL policy](docs/sql_execution_policy.md), [rendering/privacy](docs/rendering_and_privacy.md), [evaluation](docs/evaluation_contract.md), [ingestion recovery](docs/ingestion_recovery.md).

## Current status

Implementation baseline `4895c91` has recorded passes for 98 isolated backend tests and six browser contracts. [CI run 35223139147](https://github.com/Jim-lan/log-pilot/actions/runs/35223139147) passed for this revision. Abrupt transaction-crash checks and an existing-image vector smoke add recovery evidence. These checks do not measure live-model accuracy or qualify a full deployment.

Durable ingestion, bounded intake and isolated multi-turn evaluation now have regression coverage. Next designs address held-out/live-model evaluation, identity/tenant isolation, storage ownership and operational qualification. No authentication or tenant isolation exists today. Model names in configuration are identifiers, not verified quality/hardware recommendations. Cloud inference and opt-in web search can send content externally despite best-effort redaction.

Do not run reset scripts against existing data. Main Compose startup can generate demo logs and pull a model; use the separate test profile for regression work.
