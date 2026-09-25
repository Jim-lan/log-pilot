# Evaluation integrity contract v1

## Decision

The previous runner skipped request failures, looked for context in the wrong response field, discarded measured latency and wrote `eval_runs_micro` while the dashboard read `eval_runs`. Those numbers cannot establish quality. New additive tables `evaluation_runs_v1` and `evaluation_cases_v1` are the common runner/dashboard contract. Existing tables and data remain untouched and are not relabeled as trustworthy results.

A run persists its complete case roster before background execution. Cases start pending and become passed, failed, error or unscored. Every planned case remains in the denominator. A normal finish converts unprocessed cases to errors; a process crash leaves an explicitly running run and pending cases for operator investigation. There is no durable job resumption yet. Writes use short connections and transactions; cross-process DuckDB ownership remains a Phase 5 issue.

The runner reads top-level `context`, `sql`, `sql_result`, `answer` and response metadata. Latency is measured by a monotonic clock around each request, including failed requests. A missing latency remains null. Stored evidence is evaluation data and may contain sensitive material; use synthetic datasets only until the complete data policy is implemented.

## Scoring and provenance

Deterministic checks accept structured `expected_rows`, legacy `expected_sql_result`, or `expected_answer`. Structured rows compare JSON values against API `sql_rows`, preserving duplicates; `ordered: false` permits row reordering. Legacy text expectations compare actual returned strings exactly; SQL text or keyword matches alone cannot pass a case. Optional expected intent is checked in addition. Numeric type coercion and semantic answer equivalence are not inferred. Empty rows are distinct from missing/failed results. Legacy datasets without these expectations are unscored and cannot inflate pass rates. Optional `/evaluate` Ragas judge scores are separate from deterministic pass rates and initialize only on demand.

Each run records the dataset SHA-256, limit, contract version and scorer. Each case now retains API metadata with requested/returned model identifiers, temperature, provider fingerprint when available, and SHA-256 hashes of templates used in that request. API keys, provider URLs and prompt content are excluded from this provenance. Run-level placeholders remain explicit; case metadata is the execution record. Model names/fingerprints are provider claims, not verified weight hashes. The versioned six-case SQL fixture corpus is `tests/isolated/quality_cases_v1.json`. Isolated multi-turn evaluation is defined below; repeated live-model measurements remain open. Simulated shadow output is disabled: copying a primary answer does not measure a second model.

## API and display

`POST /query` accepts `persist_history: false` for stateless evaluation: neither read ordinary history nor append the interaction. This is an additive local-development contract, not identity or authorization. It does not isolate logs or vectors. Optional bounded `evaluation_context` supports multi-turn experiments without stored chat sessions.

`POST /evaluate/batch` reads only `EVALUATION_DATASET_PATH` (default `/app/tests/evaluation/golden_dataset.json`). A client-supplied `dataset_path` must match that configured path; arbitrary paths are rejected. Positive limits are bounded at 1000. `METRICS_DB_PATH` configures the storage location for both services; their defaults resolve to the same shared application data mount.

`GET /metrics` returns `schema_version: 1`, availability status, case-weighted `pass_rate_24h`, measured `avg_latency_24h`, all-time `total_runs`, and the latest ten runs with durable status. The window uses UTC run timestamps within the preceding 24 hours; pending/error/unscored cases do not count as passes. Missing databases, old-only schemas and unavailable storage return null metrics rather than invented zero scores. The UI renders null as Unavailable. Reads never create tables.

## Experiment and rollout

Disposable DuckDB tests cover a passing case, incorrect output, failed request, unfinished run, old results outside the time window, actual evidence and request latency. API tests prove ordinary history is unchanged and the dashboard reads the same schema. Browser tests protect unavailable values and existing rendering behavior.

No existing data migration or application container restart is performed by these repairs. Try the new evaluator with a synthetic configured dataset before normal use. Rollback may ignore the additive v1 tables; retain them for reconciliation rather than deleting results. These tests do not establish live-model quality, concurrent storage safety or completion of Phase 2.


## Retrieval and citation dimensions

`QueryResponse.sources` lists the retrieved KB artifacts actually assembled into local context. Each has an opaque `source_id`, content SHA-256, kind and title. IDs use the indexed node identity when available, otherwise content identity. Content hashes change when an artifact changes; an index rebuild may change node IDs. These identify the retrieved artifact, not an authenticated original document/version/span. New journaled Markdown cards retain original document/version/span metadata under `document_origin`; older artifacts may lack it.

Context includes exact `[source:ID]` markers and synthesis is instructed to use them. Unknown citation IDs are rejected deterministically before the LLM judge, with the existing two-repair limit followed by abstention. Web fallback clears local source identities and supplies attributed search-snippet records, as defined in Q04 below. Missing citations are visible in evaluation rather than silently treated as proof of support. A valid ID does not establish that the source entails the answer.

Evaluation cases may specify `expected_source_ids` and `expected_citation_ids`. Stored dimensions separate retrieval precision/recall, citation presence, citation validity and citation precision/recall. A deterministic answer or SQL expectation is still required for an overall pass; retrieval alone cannot certify answer quality. Explicit source/citation expectations must match fully for fixture acceptance. This provides reproducible attribution checks; semantic factuality, source authenticity and adversarial live-model robustness still require additional evidence.

The frontend displays retrieved artifact identifiers and hashes as escaped text beneath answers. User/model text cannot create executable source markup. Context is described to the model as evidence, not instructions to execute; this prompt guidance is not an authorization boundary.


## Q02 isolated multi-turn context (contract v2)

A flat dataset may add `conversation_id` and one-based `turn_index` to cases. Both are required together; turns for each conversation must be contiguous in dataset order, though different conversations may interleave. Case IDs remain globally unique and every turn retains its own score and latency. Limits select a prefix after validation; they never reorder turns.

The runner owns ephemeral context per conversation and per run. It sends actual prior question/answer pairs through `evaluation_context` with `persist_history:false`; no expected answer is supplied to the model. The API accepts only alternating user/assistant pairs, at most ten messages and 16,000 characters per message. Older complete pairs are dropped. Supplying context with ordinary history enabled is rejected. Stateless requests avoid constructing a history connector entirely; graph analytics remain independent of this history contract.

Wrong but successfully returned answers remain in context, so downstream evaluation measures actual error propagation. A request failure or oversized/invalid context blocks later turns only in that conversation; they are recorded as errors without making a request. Other conversations continue. Context is not a trusted identity, does not grant data access, and does not implement tenant isolation. It is discarded after execution; durable recovery remains Q06.


## Q03 versioned fixture dataset envelope

Legacy list datasets remain supported and are labeled `legacy_unpartitioned` in run provenance. A version-2 envelope records `dataset_id`, `version`, `split` (`development` or `held_out`) and `cases`; the full raw-file SHA-256 remains the content identity. Optional fixture logs and source facts support offline verification only: batch evaluation does not ingest them or send expected answers/source facts to the query API. Use the matching disposable fixture environment for quality experiments.

The new synthetic held-out regression partition is separate from the original development SQL corpus. It covers explicit time boundaries, duplicated rows, unknown services, known source facts, hostile source instructions and unsupported questions. It is published in this repository and used to test scoring; it is not a secret benchmark, proof of unseen-model performance or a live quality result. Freeze its version for comparisons, record any changes, and reserve an independently reviewed dataset for Q07 model selection.

Cases may require `expected_outcome` in addition to an exact answer/row contract, so an abstention cannot be mistaken for a validated answer. Dependency errors remain error cases, not successful empty results. Wrong-result and fabricated-source mutations must fail; each source-based expected answer has an explicit fixture fact. Semantic entailment beyond exact fixture answers remains Q04.

The new compound-filter fixtures exposed an overly restrictive SQL function check that rejected `AND`. The policy now recognizes boolean operator nodes while continuing to reject forbidden descendant functions/tables; real graph fixtures verify that valid compound queries no longer fall into repair.

## Q04 citation support and web attribution (contract v3)

Citation ID validity is distinct from support. Optional `citation_claims` fixtures
contain unique exact claim `text` (one nonempty answer line, citation markers
removed) and reviewed `supports` pairs of `source_id` and `content_sha256`.
Coverage counts expected claims with a citation, divided by expected claims plus
unexpected answer lines. Support counts cited claim/source pairs matching both the
reviewed text and retrieved artifact hash, divided by all cited pairs. Repeated
claims, unknown claims, stale hashes and unrelated but valid IDs cannot earn full
credit. Missing citations score zero; without reviewed claims these dimensions
are null, never inferred success. These conservative exact-text fixture scores
are not a general semantic entailment judge. Existing exact answer/row checks
remain required, and configured coverage/support must both equal one to pass.

Web search returns structured snippet artifacts: an opaque URL/content identity,
HTTP(S) URL, title, UTC retrieval time and SHA-256 of the exact snippet. Context
uses the same source markers as local retrieval. Invalid URLs and empty snippets
are excluded; no usable results cause the existing bounded abstention path.
Web citations remain search-snippet attribution, not verification of the full
page or its authority. Evaluation checks cited web attribution separately.
Rejected local sources are cleared on fallback. New document cards additionally
expose their recorded original document/version/span metadata without relabeling
whole-document derivation as claim support. No storage migration is required.
