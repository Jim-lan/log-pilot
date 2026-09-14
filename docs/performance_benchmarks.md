# Performance and quality evidence

The previous document listed 100% intent/syntax accuracy, approximately 90% SQL accuracy and 15–20 second latency without retained run artifacts, model revision, fixtures or reproducible measurements. Those claims are withdrawn. They must not be used to justify enterprise readiness or hardware purchases.

## Verified scope (2026-09-14)

The isolated backend suite contains 73 tests, including a versioned six-case SQL corpus. It runs real DuckDB and LangGraph with scripted model responses. Cases cover a known count, grouped aggregates, empty results, time filtering, duplicate values and adversarial log text treated as data. Both ordered and unordered row comparison preserve multiplicity. These checks establish application contracts; they do not measure how accurately a live model generates SQL or resists prompt injection.

Existing graph checks cover valid/invalid judgments, independent correction limits, private search behavior, runbook/template retrieval using synthetic dependencies, fallback evidence and abstention. The browser suite covers hostile rendering and unavailable metrics. See [test evidence](testing_baseline.md).

## Measurement prerequisites still open

Before reporting live-model quality, use a held-out versioned dataset with independently reviewed expected rows, source IDs and facts. Record input data revision, template hashes, model identifier/fingerprint, sampling settings and every failed case. Run multiple trials and report sample size, variability and exclusions. Score retrieval separately from answer correctness and optional judge scores. A model name alone is not immutable weight provenance.

Before reporting capacity, agree concurrency, ingest volume, data size, p95 latency, error rate and recovery targets. Measure a disposable deployment under load and record hardware, image/dependency revisions and resource use. No current throughput, p95 latency, memory or enterprise-readiness claim is established by the deterministic suite.

Performance improvements and model recommendations will follow measured requirements; no particular cloud provider or large model is required by this roadmap.
