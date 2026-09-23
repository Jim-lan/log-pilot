# ADR 0001: source identity and immutable document versions

Date: 2026-09-23. Status: accepted for incremental local implementation (R02). Journal integration/replay is R03; operational crash qualification is R04. This decision does not migrate existing documents or establish tenant authorization.

## Problem

The current Markdown path discovers topics, synthesizes cards and inserts documents with random IDs. It reopens a path after the acknowledgement layer already read its bytes. A retry can generate different topics/cards, create duplicate vectors and lose the connection to original text. Content-only deduplication also conflates two source documents that happen to contain the same text.

## Decision

Separate source, content version and generated artifact identity. Use a versioned canonical JSON array (UTF-8, no ASCII escaping, compact separators) for compound identities, hashed with SHA-256. Hashes are identifiers/integrity checks, not secrets or proof of authorization.

| Identity | Definition |
|---|---|
| Namespace | Operator-configured source adapter namespace; local default `local-files`. Restricted ASCII identifier, 1–64 characters. Not a user-controlled tenant claim. |
| Source key | Producer's stable relative POSIX key within namespace, e.g. `runbooks/auth.md`. Reject absolute paths, empty/dot/parent components, backslashes and control characters; do not silently normalize distinct names. |
| Source ID | `source-` + hash of `["source-v1", namespace, source_key]` |
| Content hash | SHA-256 of exact immutable UTF-8 source bytes; no newline or Unicode normalization |
| Version ID | `document-` + hash of `["document-v1", source_id, content_sha256]` |
| Card ID | `card-` + hash of `["card-v1", version_id, ordinal]`; ordinal belongs to the durably committed plan, not a fresh model response |

Identical bytes at different source keys/namespaces have equal content hashes and different source/version IDs. Repeated publication to the same source key with identical bytes is a retry. Changed bytes create a different version of that source. A rename is a different source unless a future explicit alias operation preserves identity. Replay retrieves the original namespace/key from its journal receipt; quarantine/processed filenames are transport locations, never new source identities.

The initial local watcher uses its original landing filename as the source key; nested source adapters can supply validated relative keys later. Never use arbitrary filesystem absolute paths or remote URLs as client-visible identity. Source namespaces are not authorization boundaries; I01–I04 must bind them to trusted ownership before shared use.

## Original evidence and synthesized cards

The manifest records exact byte hash, byte length and source identity. Spans are zero-based half-open byte ranges over those exact bytes. Both endpoints must be UTF-8 character boundaries; ranges must be nonempty and within the version. Store each span's hash and verify it before presenting a quote. Line numbers are display helpers, not canonical identity. CRLF and Unicode fixtures must preserve the same offsets on every platform.

Cards record version ID, stable ordinal/ID, generated text and content hash, derivation version, and source spans. A span denotes input evidence location; it does not prove that every generated claim is supported. Initially the complete document range is an honest derivation span when precise support cannot be established. Do not label a whole-document range as sentence-level citation support. Q04/E02 add finer evidence validation.

Original files remain in processed/quarantine storage and must remain recoverable through recorded transport locations plus content verification. A missing/changed original is an explicit provenance failure, not permission to invent a quote. R03 must preserve a durable source snapshot or a recoverable immutable source reference before acknowledging indexing. Any snapshot joins the raw-file sensitivity/retention inventory; no new raw text goes into operational logs.

## Journal and replay contract for R03

Use additive document journal tables under the existing local single-worker ownership contract. Store immutable source manifest and discovered topic plan before synthesis, then persist each generated card before any vector upsert. Use stable node IDs and the existing LlamaIndex-compatible metadata/upsert boundary. Do not rely on LlamaIndex auto-generated chunk IDs.

A crash before a generated response is durably recorded may regenerate it; nothing from that response may already have reached the vector store. Once a plan/card is recorded, replay uses it verbatim and skips that model call. A crash after vector upsert but before marking the job done repeats the same payload/ID. A file is acknowledged only after every planned card is durably indexed and input bytes still match. Zero/invalid topics or empty cards fail visibly. Unknown bytes and legacy interrupted Markdown remain in review rather than being silently upgraded.

Commit source-version intent before provider work. For initial rollout, reject a new version of an already registered source rather than mixing old/new cards: version activation and superseded-vector filtering require a separate tested change. R03 may support first-version indexing and same-version recovery while leaving version replacement disabled. This intentional limit preserves reliability until active-version selection is implemented.

## Updates, deletion and compatibility

A future version update stages all new cards, then switches an authoritative active-version pointer; retrieval must filter by that pointer before returning evidence. Old jobs may not reactivate an obsolete version. Delete is initially an operator-controlled tombstone that suppresses retrieval; physical deletion follows retention/backup policy and reconciliation. Neither version activation nor deletion may be advertised before retrieval enforces it.

Do not rewrite protocol-2 log fingerprints/event IDs. Preserve existing protocol-1 Markdown ledger records and random-ID vectors as legacy. R08 inventories and reconciles them on copies; no automatic deletion or guessed source ownership. If an existing legacy claim conflicts with new document registration, reject for review rather than duplicate it under a new ID.

## Alternatives and consequences

Content-only identity is simple but loses source distinction. Random IDs make retry unsafe. Topic-text identity changes with model wording. A stable source key plus immutable version and committed ordinal preserves attribution and replay while allowing future adapters. It requires a journal, source retention and explicit version selection; it does not solve multi-writer coordination, tenant permissions or semantic correctness.

## Acceptance fixtures

R02 contracts cover identical content across source keys/namespaces, same-source retry, changed version, invalid keys, Unicode/CRLF source spans and invalid UTF-8 boundaries. R03/R04 add persistence failures before/after plan/card/upsert/acknowledgement, no repeated model calls for saved work and preservation of the established log recovery tests. Revert R02's unused identity helper without data migration; once journal integration ships, retain new records and stop the worker before rollback.
