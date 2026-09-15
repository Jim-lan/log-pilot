# File acknowledgement and recovery

## Supported source contract

The watcher accepts completed immutable UTF-8 `.log` and `.md` files up to 8 MiB. Producers must write outside the final extension (for example `.tmp`), close the file, then atomically rename it into the landing directory. File-size stability is a legacy convenience check, not proof that a writer is finished. Append-only tailing and files changed after handoff are unsupported. Changed input is rejected and quarantined; producers must preserve their originals.

## Durable acknowledgement

`data/state/ingestion.sqlite3` is a local SQLite acknowledgement ledger, not the final cross-store ownership design. A file fingerprint is SHA-256 of its extension and exact bytes. Identical completed content under the same extension is treated as a retry, including a renamed copy; this is content deduplication within this local pipeline, not global event identity across sources.

The worker transactionally claims a file as processing. Pending is the initial state within that claim transaction. It records persisted after the log file's final flush and indexed only after all processing/index calls return successfully and the source still matches the original bytes. This initial ledger does not atomically commit with DuckDB or Chroma. It cannot infer which batches/index writes succeeded after a crash. A completed file whose final move fails can be retried without repeating writes.

Database, vector, parsing and runbook-processing errors propagate. The worker marks the file failed and moves it to `data/source/quarantine/<fingerprint>-<name>` where possible, retains existing DLQ records, and stops rather than allowing mixed buffers to flow into another file. Process termination leaves processing visible in the ledger. Incomplete/failed fingerprints cannot be automatically claimed again: replay could duplicate partial writes. Empty/invalid/excessive runbook topic discovery is not accepted as successful indexing.

Startup no longer invokes destructive vector retention cleanup. Retention requires a separate verified recovery procedure. Worker shutdown stops/joins the filesystem observer and does not blindly flush a possibly partially persisted batch again.

## Operator inspection

Inspect a copy of the state/database and source files before attempting recovery. A read-only ledger query is:

```sh
sqlite3 -readonly data/state/ingestion.sqlite3 'SELECT fingerprint,name,state,failure_code,updated_at FROM files ORDER BY updated_at;'
```

Do not delete ledger rows or move quarantined files back to landing as a replay shortcut. Failed writes may coexist with durable rows in `logs`. Reconcile accepted rows and vector writes first. Full automatic repair is intentionally unavailable until the next increment provides event identities and recoverable indexing work.

## Tests, limitations and next step

Synthetic tests use the real worker methods, temporary DuckDB and SQLite, with vector/model/watcher dependencies stubbed. They cover complete acknowledgement, database/vector failure, partial data remaining visible, quarantine, a move collision, safe completed-file retry, changed input, empty runbook discovery and durable interrupted claims. They do not prove vector upsert behavior or power-loss durability.

Phase 4.2 must add stable event IDs, transactional event persistence and indexing work, idempotent vector upserts, explicit replay and crash-boundary tests. Bounded queues, multi-worker claims, source namespaces, original runbook versions, quarantine retention and complete sensitive-data handling also remain open. The separate bulk loader does not yet use this ledger. SQLite here is an additive acknowledgement mechanism; Phase 5 still decides final storage ownership and migration. No existing application data or running worker was migrated or restarted by this change.

The learning point is that acknowledging a file is a durability promise. A caught exception plus a success message breaks that promise; retries become safe only when persistence is idempotent across every affected store.
