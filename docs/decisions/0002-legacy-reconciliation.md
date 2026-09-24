# ADR 0002: reconcile legacy ingestion evidence without guessing ownership

Date: 2026-09-24. Status: accepted for R08 dry-run tooling. No live-data migration or deletion is authorized by producing a report.

Legacy protocol-1 claims do not contain enough information to prove which rows/vectors committed. Random vector IDs also do not establish a source version, original span or latest pattern revision. Mapping them automatically to a new acknowledged claim could manufacture provenance or delete distinct evidence.

Operate on an offline copied snapshot, never the application's active data directory. Open Chroma only on a second disposable working copy because its client may update internal storage even during inspection. Hash the supplied snapshot before/after; fail if its bytes change. Bound snapshot size and record count. Do not initialize missing stores or import the model/embedding stack.

Produce a dry-run reconciliation report that:

- inventories legacy claims, pending claims and journaled document cards;
- derives candidate stable pattern IDs only from explicit service/cluster metadata using the existing protocol-2 identity algorithm;
- groups identical text separately from conflicting text under that candidate ID, without assuming either is newest;
- compares journaled card IDs/text hashes with copied vectors, reporting missing, mismatched and unjournaled cards;
- retains legacy runbooks without guessing a version from their filename;
- records snapshot fingerprints and counts, while omitting raw documents, prompts, card text and source filenames;
- never deletes vectors, edits ledger state, writes application databases or synthesizes an acknowledgement.

A duplicate-text candidate is not deletion approval: ownership and source identity can still differ. A conflicting group, unknown record or legacy runbook remains review-required. A reviewer must choose preserved evidence and a migration plan with restorable backups before an apply tool is designed. Real application reconciliation depends on an actual stopped/copied dataset and that review; synthetic fixtures alone cannot resolve the user's legacy records.

R08 completion evidence for the tooling is a deterministic report on mixed synthetic legacy/current data, exact source-copy preservation, accurate conflict/missing-vector reporting, bounded failure on invalid inputs and real Chroma inspection from a disposable copy. Existing data stays intact. Future destructive cleanup is separately gated by O03/O04.
