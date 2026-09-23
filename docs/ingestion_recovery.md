# File acknowledgement and recovery

## Supported source contract

The watcher accepts completed immutable UTF-8 `.log` and `.md` files up to 8 MiB. Producers must write outside the final extension (for example `.tmp`), close the file, then atomically rename it into the landing directory. File-size stability is a legacy convenience check, not proof that a writer is finished. Append-only tailing and files changed after handoff are unsupported. Changed input is rejected and quarantined; producers must preserve their originals.

## Durable acknowledgement

`data/state/ingestion.sqlite3` is a local SQLite acknowledgement ledger, not the final cross-store ownership design. A file fingerprint is SHA-256 of its extension and exact bytes. Identical completed content under the same extension is treated as a retry, including a renamed copy; this is content deduplication within this local pipeline, not global event identity across sources.

The worker transactionally claims a file as processing. Pending is the initial state within that claim transaction. It records persisted after the log file's final flush and indexed only after all processing/index calls return successfully and the source still matches the original bytes. The acknowledgement ledger remains separate from DuckDB/Chroma. Protocol 2 now records event identities, log rows and indexing payloads atomically in DuckDB; this journal resolves which structured events committed. A completed file whose final move fails can be retried without repeating writes.

Database, vector, parsing and runbook-processing errors propagate. The worker marks the file failed and moves it to `data/source/quarantine/<fingerprint>-<name>` where possible, retains existing DLQ records (new protocol-2 failures use the source quarantine and transactional outbox), and stops rather than allowing mixed buffers to flow into another file. Process termination leaves processing visible in the ledger. Incomplete/failed fingerprints require explicit replay. Only protocol-2 log files are eligible; older partial files and Markdown still require review. Empty/invalid/excessive runbook topic discovery is not accepted as successful indexing.

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

Chroma uses [upsert](https://docs.trychroma.com/docs/collections/update-data) with LlamaIndex-compatible node metadata; this preserves retrieval through the existing adapter. Legacy vector records are not deleted or reconciled, so old random-ID duplicates may still coexist. Markdown synthesis/replay, distributed workers, automatic retry scheduling and original-source retention remain future increments. Bounded queues, multi-worker claims, source namespaces, original runbook versions, quarantine retention and complete sensitive-data handling also remain open. The separate bulk loader does not yet use this ledger. SQLite here is an additive acknowledgement mechanism; Phase 5 still decides final storage ownership and migration. No existing application data or running worker was migrated or restarted by this change.

The learning point is that acknowledging a file is a durability promise. A caught exception plus a success message breaks that promise; retries become safe only when persistence is idempotent across every affected store.

The R01 vector smoke now has its own clean-build test image and CI job; it checks abrupt exit after acknowledged vector writes and reopening/replay in fresh processes. See [test commands and evidence](testing_baseline.md). This adds coverage without changing application ingestion or migrating existing vectors.

## R02 document identity design

[ADR 0001](decisions/0001-document-identity.md) defines namespace/source keys, immutable byte-hashed versions, stable card IDs and verified UTF-8 byte spans. The pure identity helper and synthetic contracts are implemented; the existing worker is not yet integrated. R03 must journal the plan and generated cards before vector writes, preserve source evidence, and gate legacy/changed-version inputs. Log protocol-2 identities remain unchanged.
