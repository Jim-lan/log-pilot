# LogPilot API reference

Implementation baseline `4895c91`, 2026-09-17. Local API: `http://localhost:8000`; evaluation: `http://localhost:8002`; MCP: port 8001. These interfaces currently lack authentication and tenant isolation. They are not public deployment contracts.

## Query

`POST /query` accepts:

```json
{"query":"How many ERROR logs are present?","persist_history":false}
```

`query` is required text. `persist_history` defaults to `true`; `false` skips normal conversation history reads and writes. Default history belongs to a shared session, not an authenticated user.

| Response field | Contract |
|---|---|
| `answer` | Answer or abstention text |
| `intent` | Graph route classification |
| `sql` | Generated SQL or null |
| `sql_result` | Legacy result text or null |
| `sql_rows` | Structured arrays of values or null; `[]` means a successful empty result |
| `context` | Selected retrieval/web evidence or null |
| `sources` | Retrieved artifact records with ID, content hash, kind, title and provenance; may be empty |
| `metadata` | Rewritten query, latency, judge feedback, outcome, retry counts, provider call counts and provenance |
| `trace` | Serialized message transcript, possibly null; not a complete execution-event audit |

Provenance includes template source hashes and per-call requested/returned model identifiers, temperature and available provider fingerprint. It does not include credentials or rendered prompt content. A validated outcome denotes completion of the configured validation process, not independently proven correctness.

The HTTP deadline defaults to 120 seconds with four active workers per API process. Synchronous work may continue after HTTP timeout while retaining its worker slot. See [budget semantics](request_budgets.md).

| Status | Typed execution code |
|---|---|
| 422 | `sql_execution_failed` |
| 429 | `call_budget_exceeded` |
| 502 | `dependency_error` |
| 503 | `query_capacity_exhausted` |
| 504 | `deadline_exceeded` or `provider_timeout` |

FastAPI request validation also uses 422 with its own validation-detail shape. Unexpected errors can still return 500 with exception text; do not assume all error paths are sanitized. Consumers must handle failed requests without interpreting them as empty successful results.

## Other API routes

| Method and route | Behavior |
|---|---|
| `GET /health` | Checks model status; not comprehensive readiness |
| `GET /history` | Shared default conversation as role/content/timestamp records |
| `GET /alerts` | Unread persisted alerts |
| `POST /alerts/{alert_id}/read` | Marks alert read; returns `{"status":"ok"}` |
| `GET /metrics` | Versioned evaluation summary; unavailable storage produces unavailable/null measurements |

Metrics use a UTC 24-hour window for recent measurements, case-weighted outcomes and a limited recent-run history. Older incompatible metrics are excluded. Consult [evaluation schema and scoring](evaluation_contract.md), rather than inferring accuracy from a single percentage.

## Evaluation service

| Method and route | Request and result |
|---|---|
| `GET /health` | Status, schema version and Ragas `on_demand` |
| `POST /evaluate/batch` | Optional `dataset_path` and `limit`; returns started status, run ID and schema version |
| `POST /evaluate` | Required `query`, `rewritten_query`, `rag_context`, `final_answer`; supplementary Ragas scores, or 503 if unavailable |

Batch `dataset_path`, if supplied, must equal the server-configured path. `limit` must be positive and at most 1000. Invalid/unavailable datasets return 400; request validation returns 422. The selected dataset must be a nonempty list with unique string case IDs and string questions.

The complete case roster is persisted before background execution. Each case calls the orchestrator with `persist_history:false`. Started does not mean completed or passed; interrupted workers can leave pending cases. The optional Ragas judge does not determine deterministic batch pass rates. Arbitrary client filesystem paths are not accepted.

## MCP surface

| Tool/resource | Current behavior |
|---|---|
| `query_logs(sql_query)` | Shared restricted analytics SQL executor; returns text |
| `ask_log_pilot(question)` | Forwards to `/query`, returns answer text, 60-second proxy timeout |
| `logs://recent` | Restricted query for the latest 50 logs |
| `logs://schema` | Fixed trusted `DESCRIBE logs` query |

The proxy currently uses default history persistence and has a shorter timeout than the API deadline. Handler errors are returned as text, not the API typed error contract. In-process handler tests do not establish SSE transport readiness. Source/evidence-rich MCP responses and scoped identity are future designs.
