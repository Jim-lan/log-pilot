# Query deadlines and provider budgets

Implemented 2026-09-11 for roadmap Step 1.2. Previous tested checkpoint: `3963756` (local commit).

## Contract

Each `/query` request receives its own monotonic deadline, LLM/search counters and sticky failure state. Context propagates through the bounded query worker and LangGraph node workers; it is reset when work ends. There is no global shared call counter.

| Operator setting | Default | Meaning |
|---|---|---|
| `LOGPILOT_REQUEST_TIMEOUT_SECONDS` | 120 | Maximum HTTP wait for a query, including history, graph and response work |
| `LOGPILOT_LLM_TIMEOUT_SECONDS` | 30 | Per-LLM-call transport timeout, capped by remaining request time |
| `LOGPILOT_SEARCH_TIMEOUT_SECONDS` | 10 | Per-search-client timeout, capped by remaining request time |
| `LOGPILOT_MAX_LLM_CALLS` | 16 | Logical generation attempts across all graph stages per request |
| `LOGPILOT_MAX_SEARCH_CALLS` | 1 | Logical search operations per request |
| `LOGPILOT_QUERY_WORKERS` | 4 | Maximum active synchronous query workers per API process; read at startup |

Settings must be positive and finite; counts must be integers. The application Compose file forwards them. Changing worker capacity requires restarting the API. No application services were restarted during development of this change.

OpenAI-compatible generation uses `max_retries=0` and explicit request timeout options. Graph repair attempts consume the same request counter rather than acquiring a new budget. Both registry and legacy configuration routes use the same adapter path. Search creates a per-call client, uses a whole-second timeout rounded down, and closes it after materializing results; less than one remaining second fails before calling that client. A search operation may involve multiple underlying HTTP requests inside its library; its logical counter is not a count of individual HTTP packets or backend attempts.

## Failure behavior

| HTTP status | `detail.code` | Meaning |
|---|---|---|
| 504 | `deadline_exceeded` | The query's overall wait expired |
| 504 | `provider_timeout` | Provider timeout or a result returned after its allotted call time |
| 429 | `call_budget_exceeded` | No provider attempts remain for this query |
| 502 | `dependency_error` | A required provider failed or returned unusable output |
| 503 | `query_capacity_exhausted` | All synchronous query slots are still occupied; no work was queued |

Errors use a stable JSON object with `code` and a sanitized `message`, never raw provider bodies, keys or URLs. An insufficient-evidence answer is different: the existing graph abstention can still return HTTP 200 with `metadata.outcome: insufficient_evidence`. Successful responses add `metadata.provider_calls` alongside existing retry metadata.

Provider failure state survives existing broad exception handlers in nodes: guards check it before and after every node, so a caught error cannot become fallback evidence or a successful answer. No SDK-generated error strings are returned as model content. Disabled search still makes no call. The simulated, unbudgeted shadow thread is disabled inside a budget-managed request.

## Cancellation and persistence limits

The asynchronous API stops waiting at its deadline. Cancellation is cooperative for synchronous Python/native work: a blocked operation cannot safely be killed in its thread. A timed-out worker therefore retains its capacity slot until it exits. New requests are rejected when all slots are occupied; they are not added to an unbounded executor queue. Provider transports receive shorter timeouts, and guards reject late results and prevent subsequent graph stages. This is bounded worker retention, not proof that an upstream server stops generation or billing.

A graph finishing after timeout fails the budget check before history saving, covered by an event-controlled HTTP test. Checks also run before persistence and before returning success. Already-started database writes cannot be undone by cancelling an HTTP wait; history's existing separate writes are not made atomic by this change. Transactional persistence and storage recovery remain Phase 5 work. Transport timeouts may describe I/O inactivity rather than total execution time, which is why the separate HTTP deadline is necessary.

These request-wide guarantees cover `/query`. Standalone callers of graph/provider modules must use `use_budget(RequestBudget.from_env())` to share a budget across operations. A provider invoked without a request context gets a standalone per-operation budget; it does not create a deadline around an entire script. Health checks get provider timeouts but are not routed through the query-worker pool. Readiness, fair per-user quotas, streaming cancellation, process-level termination and full deployment load testing remain separate work.

## Verification and learning

The isolated suite uses real HTTP dispatch, real LangGraph, temporary DuckDB and the real OpenAI SDK with an in-memory HTTP transport. Search client construction and cleanup use a test double. No live provider or search request is sent.

New checks cover monotonic expiry, remaining-time caps, cancellation, separate request contexts, sticky budget exhaustion, independent search counters, late results, real SDK timeout propagation, no hidden SDK retries, sanitized legacy failures, search cleanup, HTTP capacity rejection, delayed-worker slot retention, late-result discard and propagation across the real graph.

The design lesson is that retry limits, transport timeouts, overall deadlines and capacity limits solve different problems. All four are required to prevent stalled dependencies from consuming unlimited work. This increment exercises those controls without claiming that threads or remote computations can be forcibly cancelled.

Rollback: restore the prior code/config together from the local checkpoint; no schema migration is required. Reverting restores the previous unbounded HTTP wait, so it should not be used as an operational workaround for a slow provider. Exact execution results are in [testing_baseline.md](testing_baseline.md).

## Deterministic provider regression timing (2026-09-23)

CI run 35872914196 exposed a test setup race: SDK initialization consumed the fixture's five-second wall-clock request budget before the mocked timeout. Provider tests now inject a controlled monotonic clock and assert an exact three-second remaining timeout after advancing it by two seconds. Real SDK transport and single-attempt assertions remain in place. Application deadline behavior is unchanged.

## Q05 structured execution trace

`/query` now returns trace schema v2: bounded request, node and provider span
records instead of chat messages. Each record carries a generated request ID,
unique stage ID, parent stage ID, stage name/kind, one-based attempt number,
monotonic start offset/duration in milliseconds, outcome and a fixed failure
code. Validation rejection differs from provider failure and final abstention.
No prompts, answers, SQL, history, tool arguments, exception strings or hidden
reasoning are copied into these records. Existing answer/evidence fields remain
separate. The evaluator retains these events with the case evidence.

A request stores at most 256 spans including its root; metadata reports dropped
spans. Snapshots are detached from the worker and ordered by stage start. Typed
failures, unexpected query failures, capacity rejection and HTTP timeout return
request ID, trace version and events in `detail`. Invalid request bodies still
use FastAPI validation errors before request execution. At HTTP timeout the root
is failed but a blocked worker's spans can remain `running` with null duration;
this is a point-in-time response, not a claim that synchronous work was killed.
Later worker completion cannot rewrite the returned snapshot or root outcome.

Tracing follows the existing request ContextVar through graph workers and uses
locked bounded storage. Standalone graph calls still need `use_budget` to obtain
a shared request trace. Provider attempts denied by a budget are traced but do
not increment actual provider-call counters. This is an API contract version
change for trace consumers; the frontend does not consume the old transcript.
No database migration or deployment is required; roll back API and evaluator
code together while retaining existing records with their trace version.
