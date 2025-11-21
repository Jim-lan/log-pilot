# Detailed System Workflow

## 1. High-Level Architecture Flow

```text
┌──────────────────────────────┐
│ source_systems               │
│ • data/landing_zone (Files)  │
│ • Kafka Stream (Mock)        │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ ingestion_layer              │
│ • BulkLoaderJob (History)    │
│ • LogIngestor (Real-Time)    │
│ • PIIMasker (Governance)     │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ standardization_engine       │
│ • Drain3 (Template Mining)   │
│ • Schema Registry (Cache)    │
│ • LogEvent (Golden Schema)   │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ storage_layer (Lakehouse)    │
│ • DuckDB (Structured Logs)   │
│ • JSON Context (Dynamic)     │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ intelligence_layer (Planned) │
│ • ChromaDB (Vector Store)    │
│ • Pilot Orchestrator (Agent) │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ api_gateway (Planned)        │
│ • Chat Interface             │
│ • REST Endpoints             │
└──────────────────────────────┘
```

## 2. Detailed Data Flow (Step-by-Step)

### Phase 1: Bulk Loader (Historical Data)
**File**: `services/bulk-loader/src/log_loader.py`

1.  **Initialization**: `BulkLoaderJob` initializes `DuckDBConnector` and `MockDrain3`.
2.  **File Scanning**: `run()` scans `data/landing_zone/` for `.log` files.
3.  **Line Processing** (`process_file`):
    *   **Read**: Iterates through file line by line.
    *   **Parse**: Splits line into standard fields (Timestamp, Severity, Service, Body).
    *   **Template Mining**: Calls `self.miner.transform(body)` to convert "User 123" -> "User <*>".
    *   **Context Extraction**: Parses key-value pairs (e.g., `user_id=101`) into a `context` dictionary.
    *   **Standardization**: Creates a `LogEvent` object.
4.  **Batch Insertion**:
    *   Accumulates logs in a list.
    *   When list size >= 100, calls `db.insert_batch()`.

### Phase 2: Ingestion Worker (Real-Time)
**File**: `services/ingestion-worker/src/main.py`

1.  **Initialization**: `LogIngestor` initializes `MockKafkaConsumer`, `MockSchemaRegistry`, `DuckDBConnector`, and `PIIMasker`.
2.  **Consumption**: `run()` iterates over `self.consumer` (simulating Kafka stream).
3.  **Log Parsing** (`parse_log`):
    *   **Raw Split**: Separates metadata from the message body.
    *   **PII Masking (Body)**: Calls `self.pii_masker.mask_text(body)` to redact sensitive info (Emails, IPs, CCs, SSNs) *before* further processing.
    *   **Template Lookup**: Calls `self.registry.get_template(safe_body)` to get the standardized template.
    *   **Context Extraction**: Extracts `key=value` pairs from the log.
    *   **PII Masking (Context)**: Iterates through context values and applies `mask_text` again to ensure no PII leaks in structured data.
    *   **Object Creation**: Returns a `LogEvent` model.
4.  **Batching**:
    *   Appends `LogEvent` to `self.batch_buffer`.
    *   Checks if buffer size >= 5.
5.  **Persistence** (`flush_batch`):
    *   Calls `self.db.insert_batch(buffer)`.
    *   `DuckDBConnector` serializes the `context` dict to JSON and executes the SQL `INSERT`.

## 3. Key Functions & Components

| Component | Function | Description | Source File |
|-----------|----------|-------------|-------------|
| **PII Masker** | `mask_text(text)` | Applies regex patterns to redact sensitive data. | `shared/utils.py` |
| **Schema Registry** | `get_template(content)` | Returns the standardized template for a log line. | `services/ingestion-worker/src/main.py` |
| **DB Connector** | `insert_batch(logs)` | Inserts a list of LogEvents into DuckDB efficiently. | `shared/db_connectors.py` |
| **Log Event** | `LogEvent` (Class) | Pydantic model defining the Golden Standard Schema. | `shared/log_schema.py` |
