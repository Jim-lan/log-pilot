# Protected feature coverage and legacy harness disposition

Q01 checkpoint, 2026-09-24. This maps the contracts in the [roadmap](enterprise_roadmap.md) to maintained verification and explicit remaining gates. Use `scripts/run_isolated_tests.py` or standalone test Compose; do not interpret a bare `pytest` discovery of historical scripts as the release suite.

## Coverage map

| Protected contract | Maintained verification | Remaining work |
|---|---|---|
| SQL counts, grouping, time filters, duplicate rows and empty versus failed results | `tests/isolated/test_graph.py`, `quality_cases_v1.json`, `test_sql_policy.py`, `test_evaluation.py`; real LangGraph/DuckDB with scripted generation | Held-out/live-model quality Q03/Q07; tenant/process boundaries I03/D05 |
| Runbook retrieval, citation IDs, unrelated evidence, fallback and abstention | `test_graph.py`; real vector adapter/replay integration; `test_evaluation.py` retrieval/citation scores | End-to-end relevance with actual embedding/model Q03/Q07; claim support/web attribution Q04 |
| First query, follow-up, serialized history and stateless evaluation | `test_api_mcp.py`, `test_environment.py`; temporary real databases | Multi-turn evaluation Q02; trusted user/workspace isolation I01–I04 |
| Parsing, redaction, source identity, durable ingestion and replay | `tests/test_parser_formats.py`, `test_privacy.py`, `test_ingestion.py`, `test_document_identity.py`; log/document process-crash programs | Actual legacy-data review after R08 report; distributed ownership S06; source policies I05 |
| Bounded intake, retries and recovery ordering | `test_file_intake.py`, `test_ingestion.py`; restart/crash integration | Capacity and disk exhaustion O01/O02; producer disk quotas not implied by memory bounds |
| UI SQL/evidence/code/history/errors/alerts remain readable and inert | Six Playwright browser contracts in `tests/frontend/rendering.test.mjs` | Full deployment navigation/authentication D07/I04 |
| Alerts detect a spike, remain quiet on quiet data, obey cooldown and persist/dismiss | New `test_sentry.py`, persistence coverage in `test_environment.py`; real temporary DuckDB, controlled UTC clock | Per-service/workspace baselines, authorization and simultaneous outages O05/I04 |
| MCP query/recent/schema/forwarding and failure behavior | `test_api_mcp.py` imports real handlers; shared SQL policy exercised | Real SSE transport and full service wiring D07; identity I04 |
| Evaluation totals, failure denominator, evidence, latency, availability and provenance | `test_evaluation.py`, `test_graph.py`, `test_api_mcp.py` | Multi-turn Q02, interrupted-run recovery Q06, repeated live quality Q07 |
| Local dependency outages and repeatable installation | Provider/deadline/capacity contracts, clean Docker backend/vector jobs and browser CI | Disposable complete application startup D01–D07; health is not readiness |

Passing these checks does not complete the unresolved gates. In particular, a mocked retrieval node is not evidence of embedding relevance and MCP handler tests do not establish transport compatibility.

## Legacy test/script disposition

No historical script was executed on application data during this review. Preserve them as references; migrate useful assertions into the isolated runner before using them as evidence.

| Legacy files | Observed limitation | Maintained replacement / disposition |
|---|---|---|
| `tests/test_mcp_server.py` | Imports removed `get_db`, references obsolete `services/mcp-server`, mocks old MCP package and connector internals | Superseded by `test_api_mcp.py`; real transport is D07 |
| `tests/test_pilot_api.py`, `tests/e2e/test_full_flow.py` | Import application API at collection time, alter global modules or patch obsolete graph/DB symbols | Superseded by isolated API/graph contracts; not full-stack tests |
| `tests/test_agentic_rag.py`, `verify_agentic_scenarios.py`, `verify_rewrite.py`, `verify_e2e_full.py`, `reproduce_reliability.py` | Historical mocks/state/routes and prompt assumptions; imports can initialize application dependencies | Superseded by real-graph scripted contracts; retain as scenario references for Q03 |
| `tests/test_alert_persistence.py`, `verify_sentry.py` | Use default storage; the Sentry script deletes alerts and starts a background service | Replaced by isolated persistence and Sentry contracts; never a production verification command |
| `tests/test_drain3_integration.py`, `check_drain3.py` | Manual mining diagnostics; writes/deletes a data-directory state file or prints rather than asserting failure | Replaced by real pinned Drain3 clustering/save/reload assertions in `test_template_miner.py`; worker crash tests still substitute mining |
| `tests/verify_architecture.py` | Model/KB imports and cleanup of temporary-looking paths do not isolate all connector history/alert effects | Real adapter/database/crash checks replace its storage claims; full stack remains D07 |
| `tests/test_llm_client.py` | Historical constructor/config mocks and exact-call assumptions | Superseded by real SDK mocked-transport tests in `test_budgets.py` |
| `tests/debug_ragas.py`, `tests/evaluation/judge*.py` | Live endpoints/model imports, legacy metric contracts or ordinary history usage | Diagnostic references only; use versioned evaluation runner and Q07 controlled experiments |
| `tests/test_parser_formats.py` | Maintained parser assertions | Explicitly included in isolated runner; retained in place |

## Q01 fixes discovered by coverage

Sentry had no upper bound on its current window: future-dated events could be counted as current errors. The repaired service uses one explicit UTC observation time for `(now−1 minute, now]` and `(now−6 minutes, now−1 minute]`, with an injectable clock for deterministic fixtures. It preserves the existing global ratio/minimum/cooldown behavior; O05 still owns scoped alert design.

The new real Drain3 contract reproduced a reload failure after explicit `save_state()`: the wrapper wrote a pickled list while Drain3 expected its native compressed tree representation. Saving now delegates to Drain3. The contract verifies generalized templates, stable cluster IDs, message counts and a second cluster across repeated saves/reloads. Existing corrupt snapshots are not automatically rewritten or deleted; recovery of such artifacts requires inspection.

Q01 is complete with 138 passing contracts in the rebuilt isolated Docker image, including the real pinned miner. The remaining gaps above belong to their named Q/I/S/D/O tasks and do not become hidden expected failures.
