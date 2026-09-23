# File acknowledgement and recovery

## Supported source contract

The watcher accepts completed immutable UTF-8 `.log` and `.md` files up to 8 MiB. Producers must write outside the final extension (for example `.tmp`), close the file, then atomically rename it into the landing directory. File-size stability is a legacy convenience check, not proof that a writer is finished. Append-only tailing and files changed after handoff are unsupported. Changed input is rejected and quarantined; producers must preserve their originals.

## Durable acknowledgement

`data/state/ingestion.sqlite3` is a local SQLite acknowledgement ledger, not the final cross-store ownership design. A file fingerprint is SHA-256 of its extension and exact bytes. Identical completed content under the same extension is treated as a retry, including a renamed copy; this is content deduplication within this local pipeline, not global event identity across sources.

The worker transactionally claims a file as processing. Pending is the initial state within that claim transaction. It records persisted after the log file's final flush and indexed only after all processing/index calls return successfully and the source still matches the original bytes. The acknowledgement ledger remains separate from DuckDB/Chroma. Protocol 2 now records event identities, log rows and indexing payloads atomically in DuckDB; this journal resolves which structured events committed. A completed file whose final move fails can be retried without repeating writes.

Database, vector, parsing and runbook-processing errors propagate. The worker marks the file failed and moves it to `data/source/quarantine/<fingerprint>-<name>` where possible, retains existing DLQ records (new protocol-2 failures use the source quarantine and transactional outbox), and stops rather than allowing mixed buffers to flow into another file. Process termination leaves processing visible in the ledger. Incomplete/failed fingerprints require explicit replay. Protocol-2 logs and new journaled Markdown versions support explicit replay; legacy partial Markdown requires review. Empty/invalid/excessive runbook topic discovery is not accepted as successful indexing.

Startup no longer invokes destructive vector retention cleanup. Retention requires a separate verified recovery procedure. Worker shutdown stops/joins the filesystem observer and does not blindly flush a possibly partially persisted batch again.

## Operator inspection

Inspect a copy of the state/database and source files before attempting recovery. A read-only ledger query is:

```sh
sqlite3 -readonly data/state/ingestion.sqlite3 'SELECT fingerprint,name,state,failure_code,updated_at FROM files ORDER BY updated_at;'
```

Do not delete ledger rows or move quarantined files back to landing as a replay shortcut. Stop the normal worker, preserve a backup, and resume a protocol-2 log using the exact source bytes and an unused processed destination:

```sh
python services/ingestion-worker/src/main.py --replay data/source/quarantine/FILE.log --processed-file data/source/processed/RECOVERED.log
```

The CLI acquires a local exclusive file lock before starting either a watcher or replay. Do not run this command concurrently with an older worker that does not honor the lock. Recover outstanding files before accepting newer pattern updates. This is a single-worker local recovery procedure, not a distributed lease or multi-writer guarantee. Protocol-1 partial records are rejected even with `--replay`; manually reconcile them first. Ordinary starts never force replay.

## Tests, limitations and next step

Synthetic tests use the real worker methods, temporary DuckDB and SQLite, with vector/model/watcher dependencies stubbed. They cover complete acknowledgement, database/vector failure, partial data remaining visible, quarantine, a move collision, safe completed-file retry, changed input, empty runbook discovery and durable interrupted claims. An additional real Chroma/LlamaIndex smoke verifies repeat/update/retrieval for a stable vector ID. Abrupt child-process exits immediately before/after DuckDB COMMIT verify transaction recovery, but not disk/power-loss durability.

Protocol-2 log event IDs combine the file fingerprint with its zero-padded physical line number; duplicate text on different lines remains separate events. `ingestion_events_v1` and `ingestion_outbox_v1` are additive DuckDB tables. A transaction inserts log rows, event keys and pattern payloads together. Committed lines are skipped before re-mining on replay. Remaining pattern jobs are upserted by service/cluster identity and marked done only after success. A crash after vector write repeats the same upsert, preserving one vector. Pattern work is retained even when the miner says a template is unchanged, since mining may have advanced before a failed database commit.

Chroma uses [upsert](https://docs.trychroma.com/docs/collections/update-data) with LlamaIndex-compatible node metadata; this preserves retrieval through the existing adapter. Legacy vector records are not deleted or reconciled, so old random-ID duplicates may still coexist. Journaled Markdown synthesis/replay and original snapshots are described in R03 below. Distributed workers, automatic retry scheduling and lifecycle retention remain future increments. Bounded queues, multi-worker claims, source namespaces, original runbook versions, quarantine retention and complete sensitive-data handling also remain open. The separate bulk loader does not yet use this ledger. SQLite here is an additive acknowledgement mechanism; Phase 5 still decides final storage ownership and migration. No existing application data or running worker was migrated or restarted by this change.

The learning point is that acknowledging a file is a durability promise. A caught exception plus a success message breaks that promise; retries become safe only when persistence is idempotent across every affected store.

The R01 vector smoke now has its own clean-build test image and CI job; it checks abrupt exit after acknowledged vector writes and reopening/replay in fresh processes. See [test commands and evidence](testing_baseline.md). This adds coverage without changing application ingestion or migrating existing vectors.

## R02 document identity design

[ADR 0001](decisions/0001-document-identity.md) defines namespace/source keys, immutable byte-hashed versions, stable card IDs and verified UTF-8 byte spans. The identity helper is integrated for new Markdown files by R03 below. R03 must journal the plan and generated cards before vector writes, preserve source evidence, and gate legacy/changed-version inputs. Log protocol-2 identities remain unchanged.

## R03: journaled Markdown recovery (2026-09-23)

New Markdown files use additive `document_versions_v1` and `document_cards_v1` tables in `data/state/ingestion.sqlite3`, separate from the legacy `files` rows. The version row retains the exact original bytes, source manifest, committed topic plan, state and last recorded file location. Card rows retain immutable generated payloads and per-card index acknowledgements. This raw snapshot is sensitive source data: include the ledger in backup, access and eventual retention policies; do not expose it in diagnostics.

The worker uses its initial byte snapshot throughout discovery/synthesis. It persists the original before provider work, persists the validated 1–32 unique-topic plan before synthesis, and persists each nonempty card (maximum 65,536 characters) before vector upsert. A replay never regenerates a saved card or plan. Lost vector acknowledgements repeat the same stable-ID upsert. Saved source spans currently identify the entire original input, not claim-level supporting sentences.

New source identity is `local-files` plus the original landing filename. Identical bytes under another filename are a different source. Same-key changed bytes are rejected for migration review until active-version filtering exists. Any matching legacy Markdown ledger claim is also rejected for review; existing random-ID vectors are not automatically reconciled. The default namespace does not establish tenant isolation.

Stop the normal worker and inspect the journal read-only before replay. For a quarantined/renamed document, supply the original recorded version ID explicitly:

```sh
sqlite3 -readonly data/state/ingestion.sqlite3 'SELECT version_id,state,failure_code,location FROM document_versions_v1;'
python services/ingestion-worker/src/main.py --replay data/source/quarantine/DOCUMENT.md --document-id document-RECORDED_HASH --processed-file data/source/processed/RECOVERED.md
```

The example ID is a placeholder; use the journal value. Replay verifies exact original bytes and refuses an unknown ID or changed content. A file still at its original landing name can be resumed with `--replay` without `--document-id`. Ordinary ingestion refuses incomplete versions. Final move failures retain indexed state; retry only moves the file. A crash between file move and location update can leave a stale location hint; the journal's original bytes and version remain authoritative. This is recoverable provenance, not an atomic filesystem/SQLite transaction.

Faults quarantine failed input where possible and stop the worker. Successful acknowledgement requires every planned card indexed and unchanged source bytes. Partial vectors can be visible before full file completion; document-level atomic retrieval visibility is not claimed. R04 extends abrupt-process fault testing; R05/R06 still supply bounded queues and automatic retry policy. Original snapshots can grow without a retention policy, so shared deployment remains gated.

Rollback note: preserve the new document journal and original snapshots. Before running an older worker, stop document intake and remove pending Markdown from that worker's watched directory through a reviewed preservation procedure; an older binary does not understand the new journal and could duplicate vectors. Rolling back code alone is not a safe Markdown replay strategy.

R04 adds abrupt-process tests around actual log and document worker operations, including acknowledgement and final file movement. See [qualification scope](testing_baseline.md). A process dying after the final move can leave only a stale location hint; the indexed journal and immutable snapshot remain intact. The tests deliberately keep process failure distinct from disk/power loss and preserve the requirement for an explicit known-version replay.

## R05: bounded intake by directory polling

The local source adapter now polls the landing directory instead of accumulating Watchdog events. It scans with `os.scandir`, retains at most `LOGPILOT_INGEST_QUEUE_SIZE` paths (default 256, supported 1–10,000), drains that batch, then scans again. One additional file may be in processing. Files beyond the bound remain on disk and are discovered by later scans/restarts. The directory is the durable backlog; this bounds memory, not disk usage, ingest latency or producer volume.

Only regular non-symlink `.log`/`.md` entries are admitted. Temporary extensions and directories are ignored. Producers must still close and atomically rename completed files. The old size-stability delay is removed: an unchanged size never proved completion, and it incorrectly skipped empty log files. The worker's byte verification remains. Polling defaults to one second while idle and wakes on close without a background observer thread. Source ordering is filesystem enumeration order, not event-time order. Failed processing still stops intake; R06/R07 govern retries and pending recovery ordering.

Processed-file collisions choose a fresh UUID suffix and preserve the existing file; the worker still refuses an occupied destination. R05 tests saturate a two-path intake with seven files, verify eventual drain/no duplicate admission, atomic publication, empty files, collision preservation, restart discovery, disappeared paths, invalid limits and prompt idle shutdown. No production watcher was restarted as part of verification.
