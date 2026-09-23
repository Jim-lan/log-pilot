# LogPilot implementation task tracker

Updated 2026-09-23. Derived from the [system design](system_design.md) and [enterprise roadmap](enterprise_roadmap.md). Implementation baseline: `4895c91`. This is the actionable queue for remaining work; unchecked tasks are planned, not started by this documentation update. Task groups follow the new design's seven stages; the older roadmap phase numbers differ and are mapped below.

## Current position and next move

Already implemented: bounded query orchestration, initial rendering/redaction controls, deterministic evaluation contracts, artifact/citation checks, restricted SQL, truthful file acknowledgement and protocol-2 log replay with a transactional index outbox. Do not rebuild these features; extend their existing tests and contracts.

Recorded baseline evidence is 98 backend tests, six browser contracts and transaction-crash checks. The separate real-vector smoke used an existing image. These are historical results for the baseline, not new tests run on 2026-09-23. Full-stack readiness and live-model quality remain unproven.

**R01 is verified. R02 passed [CI run 35873720364](https://github.com/Jim-lan/log-pilot/actions/runs/35873720364). R03 passed CI. R04 fault qualification passes locally; next is R05 bounded intake.** Each remains a separately reviewable change. Keep existing log replay behavior protected throughout.

The design-document checkpoint was committed and pushed as `f39c4c0`. The user authorized sequential implementation and automatic commit/push on 2026-09-23. Each task still requires its own verification; deployment and destructive migration are separate gates.

## Ordered work groups

| Order | Group | Priority and dependency | Exit outcome |
|---|---|---|---|
| 1 | R — ingestion recovery | Next; extends current journal/outbox | Logs and documents recover without false acknowledgement or logical duplication |
| 2 | Q — measurable quality | Before model/retrieval experiments; source scoring depends on R02 | Reproducible evidence for answer quality, failure and multi-turn behavior |
| 3 | I — identity and data scope | Required before shared access; coordinate design with S02 | Every surface enforces user/workspace ownership |
| 4 | S — storage ownership | Define interfaces/ADR early; scoped migrations depend on I01 | Explicit owners, safe concurrency and exercised migrations |
| 5 | D — deployment and execution boundaries | Test against selected ownership and identity design | Reproducible disposable deployment with bounded failures |
| 6 | O — operational qualification | Define objectives early; pilot gate after R–D | Measured capacity, recovery, retention and incident handling |
| 7 | E — optional enhancements | Deferred until pilot gates pass | One measured capability improvement per experiment |

Groups are execution priorities, not instructions to postpone all security design until group 3. Identity, ownership, data policy and numeric objectives should be agreed before dependent schemas or deployment choices are finalized. No shared pilot until all applicable R–O gates pass.

## R — finish ingestion recovery (roadmap 4.1–4.3 and 0.2)

| Done | ID | Task | Completion evidence / dependency |
|---|---|---|---|
| [x] | R01 | Add clean-install Chroma/LlamaIndex upsert/recovery smoke to CI | Verified locally and in [CI run 35873358011](https://github.com/Jim-lan/log-pilot/actions/runs/35873358011), commit `5b366f7`; locked clean image and abrupt process restart/replay |
| [x] | R02 | Design document identity, source namespace, immutable version, source spans and update/delete semantics | [ADR 0001](decisions/0001-document-identity.md) and identity/span contracts verified locally and in Docker (101 tests); runtime integration is R03 |
| [x] | R03 | Implement durable Markdown indexing journal and idempotent replay | Implemented for new documents; 109 backend checks and real vector restart smoke pass locally; raw snapshots and plans/cards persist before upsert; [CI run 35874484501](https://github.com/Jim-lan/log-pilot/actions/runs/35874484501) passed for `3387b65` |
| [x] | R04 | Extend process-crash and outage tests across all document/log acknowledgement boundaries | Verified locally: 16 document boundaries with real vectors, 14 log boundaries with durable vector double, each followed by two replays; remote CI pending |
| [ ] | R05 | Bound the watcher/work queue and implement backpressure | Saturation remains bounded; unaccepted inputs remain recoverable; no silent drops |
| [ ] | R06 | Add bounded retry/backoff and quarantine inspection/replay workflow | Explicit terminal/retryable states, redacted diagnostics; permanent failures do not loop forever or block unrelated work |
| [ ] | R07 | Enforce pending-work ordering and exercise shutdown/restart recovery | Old pending pattern versions cannot overwrite newer ones; ownership lock and graceful shutdown tested |
| [ ] | R08 | Provide legacy ledger/vector reconciliation on copied data | Inventory protocol-1/random-ID artifacts; dry-run mapping and reconciliation before any deletion; preserve rollback evidence |
| [ ] | R09 | Repair timestamp/retention semantics for active patterns | Boundary tests retain still-active templates despite old first occurrence; destructive cleanup stays disabled until O03/O04 |

R02 changes the ingestion design; it must preserve compatibility with already acknowledged protocol-2 files. Append-only tailing and distributed ingestion are separate future adapters/topologies, not implicit promises of these tasks.

## Q — establish trustworthy quality evidence (roadmap 0.2, 1.1 and 2)

| Done | ID | Task | Completion evidence / dependency |
|---|---|---|---|
| [ ] | Q01 | Close core feature coverage gaps and triage legacy test harnesses | Map each protected feature to a passing test or explicit open task; preserve SQL, RAG, history, alert and failure behavior |
| [ ] | Q02 | Add isolated multi-turn evaluation conversations | Evaluation turns share only their own context; follow-up/history cases pass without touching ordinary user history |
| [ ] | Q03 | Expand held-out fixtures with expected rows, source facts and adversarial/unknown cases | Wrong answers, empty results, fabricated evidence and dependency errors are distinguishable; dataset split/version recorded |
| [ ] | Q04 | Define and test citation coverage, support and web evidence attribution | Depends R02/Q03; valid-ID-but-unsupported claims fail the relevant score; missing citations and web sources handled explicitly |
| [ ] | Q05 | Replace transcript-only trace with structured stage events | Request/stage IDs, attempts, timing, outcome and failure reason; no hidden reasoning or raw secrets required |
| [ ] | Q06 | Make interrupted evaluation runs recoverable and provenance complete | Pending cases resume safely or end explicitly interrupted; model/template/scorer identities and dashboard totals reconcile |
| [ ] | Q07 | Run repeated live-model baseline and establish release thresholds | Depends Q02–Q06; record configuration, dataset, variability, latency and token/cost availability; separate deterministic and judge scores |

Q07 is an explicit measured experiment, not a claim that a different model is better. Provider access, suitable hardware and representative non-sensitive data must be available before running it.

## I — identity, authorization and sensitive data (roadmap 3.1 and 3.3)

| Done | ID | Task | Completion evidence / dependency |
|---|---|---|---|
| [ ] | I01 | Record identity provider, workspace and conversation ownership design | ADR includes roles, local development identity, service identities and restricted legacy shared history |
| [ ] | I02 | Implement authenticated identity and conversation ownership | Depends I01; identity comes from trusted authentication; guessed conversation IDs cannot grant access |
| [ ] | I03 | Enforce SQL/vector source scope outside model instructions | Depends I01 and R02 source identity; cross-workspace SQL/retrieval denied even with adversarial prompts |
| [ ] | I04 | Apply authorization to history, alerts, metrics, evaluation and MCP | Depends I02/I03; complete read/write cross-user/workspace denial matrix; no alternate endpoint bypass |
| [ ] | I05 | Complete sensitive-data lifecycle and provider/embedding egress policy | Inventory raw files, runbooks, queries, prompts, vectors, diagnostics and backups; supported redaction/egress rules tested |
| [ ] | I06 | Add intentional CORS, per-identity quotas and consistent public errors | Coordinate D03/D06; reject disallowed origins/overload; avoid exception/secret leakage across API and MCP |

## S — explicit storage ownership (roadmap 5)

| Done | ID | Task | Completion evidence / dependency |
|---|---|---|---|
| [ ] | S01 | Introduce repository interfaces and explicit initialization | Contract tests protect log, conversation, alert, evaluation and vector behavior; reads do not mutate schema/catalog through constructors |
| [ ] | S02 | Decide ownership topology with measured concurrency requirements | ADR compares one owner versus server storage; includes vectors and ingest ledger; coordinate I01 and O01 |
| [ ] | S03 | Build additive migration, backup and reconciliation tooling | Depends S01/S02; copied data backfills reconcile; restore tested; rollback retains writes made after cutover |
| [ ] | S04 | Migrate history/alerts to selected ownership model | Depends I01/S03; scoped legacy handling and concurrent chat/Sentry operations verified |
| [ ] | S05 | Migrate evaluation ownership | Depends S03/S04; run/case counts, metrics and interrupted-run behavior preserved |
| [ ] | S06 | Establish analytics, vector and ingestion-ledger ownership | Depends S02/S03; migrate only where justified; concurrent ingest/query/index tests show no lost writes or unexplained lock failures |

Do not assume PostgreSQL, a vector server or distributed infrastructure has already been selected. A migration is not complete when only the happy-path copy succeeds.

## D — deployable, bounded runtime (roadmap 3.2 and 6.1)

| Done | ID | Task | Completion evidence / dependency |
|---|---|---|---|
| [ ] | D01 | Pin runtime dependencies/images and verify model configuration | Clean build is reproducible; supported provider/model configuration and compatibility documented |
| [ ] | D02 | Separate model preparation and demo generation from normal startup | Normal startup does not generate logs/copy demo catalogs or unexpectedly pull models |
| [ ] | D03 | Provide configurable same-origin frontend/service routing | No hardcoded deployment origin dependency; authentication/CORS contracts from I06 preserved |
| [ ] | D04 | Add liveness/readiness, startup/restart policies and resource limits | Dependencies unavailable or storage unhealthy produce meaningful readiness failure; recovery behavior tested |
| [ ] | D05 | Isolate SQL execution in a bounded worker process | Preserve parser/engine controls; bound connection acquisition, execution and response bytes; cancellation cleans up without harming subsequent requests |
| [ ] | D06 | Add request IDs, stage metrics and redacted operational diagnostics | Align Q05/I05; distinguish overload, provider failure and no-data outcomes; check logs for secret leakage |
| [ ] | D07 | Add disposable full-stack and real MCP transport tests | Depends selected R/I/S/D contracts; UI/API/ingestion/evaluation/MCP integration, provider outage and startup failure exercised with synthetic data |
| [ ] | D08 | Rehearse versioned deployment and rollback | Depends S03/D07; configuration/image/schema compatibility and post-cutover write preservation demonstrated |

## O — qualify the controlled pilot (roadmap 4.3 and 6.2)

| Done | ID | Task | Completion evidence / dependency |
|---|---|---|---|
| [ ] | O01 | Agree measurable workload, quality and operational objectives | Record data volume, concurrent users, ingest rate, p95 latency, error rate, recovery time (RTO) and acceptable data loss (RPO); no invented targets |
| [ ] | O02 | Run load/soak and failure drills | Depends O01 and deployable R–D work; include model outage, lock contention, restarts, queue saturation and disk exhaustion |
| [ ] | O03 | Implement retention/deletion across all retained artifacts | Depends I05/R09/S ownership; raw files, vectors, history, evaluation and backups covered; deletion cannot orphan required evidence |
| [ ] | O04 | Exercise backup and complete restore in a clean environment | Restore databases, ledger, vectors and required configuration consistently; measured RTO/RPO meet O01 |
| [ ] | O05 | Improve Sentry with scoped baselines and cooldowns | Service/workspace scope respected; quiet periods and simultaneous failures tested; alert explains its triggering evidence |
| [ ] | O06 | Write operator/incident runbooks and approve a limited pilot | Depends all applicable R–O gates; drill report, audience, observation window and stop criteria recorded before shared use |

## E — optional enhancements after the pilot gate (roadmap 7)

| Done | ID | Task | Completion evidence / dependency |
|---|---|---|---|
| [ ] | E01 | Improve retrieval with scope/time filters, deduplicated windows and optional reranking | Held-out retrieval improves within evidence/latency budgets; isolation and citation accuracy preserved |
| [ ] | E02 | Add version-aware, evidence-checked runbook answers | Build on R02/Q04; current original spans support claims; superseded sources and unknown answers handled correctly |
| [ ] | E03 | Add streaming, stage progress and real cancellation | Clear incomplete/final/error states; cancellation releases supported work; authorized evidence remains safely rendered |
| [ ] | E04 | Add scoped/versioned caches | Permission, model/prompt and data-version changes cannot reuse unauthorized or stale results |
| [ ] | E05 | Implement genuine independent shadow comparisons | Separate executions, sampling and cost caps; complete records; primary latency stays within objective |
| [ ] | E06 | Add one read-only external log source | Separate adapter ADR: scoped credentials, source identity, checkpoint/replay, quotas/cost and explicit outages; existing contracts preserved |
| [ ] | E07 | Convert reviewed feedback into offline experiments and regression cases | No automatic prompt mutation from untrusted feedback; held-out improvement required before rollout |

## Tracking and completion rules

There are **49 tracked tasks**: R 9, Q 7, I 6, S 6, D 8, O 6 and E 7. E tasks are optional enhancements, not fixes required to finish the core hardening work. A row may require several small PRs; these counts are not estimates of days or release readiness.

For each task, record owner, status, design/ADR, change/PR reference, exact test revision/results, migration impact and rollback evidence. Mark complete only when its stated evidence exists. Use planned → in progress → verified; record blocked dependencies explicitly. Update the tracker and focused design together.

Keep one behavior change per reviewable increment. Run relevant isolated regressions and protect established happy paths. Use copied/disposable data for migrations and fault injection. Stop rollout on authorization leakage, missing/duplicated accepted data, unexplained error growth or failed recovery. Do not combine identity, storage and model changes in one release.
