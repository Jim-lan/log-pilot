Architecture Design Document: GenAI LogPilot

1. Executive Summary

GenAI LogPilot is an intelligent "Log Agent" capable of ingesting massive volumes of system logs to provide natural language querying, anomaly detection, failure categorization, and high-level status reporting.

The system moves beyond simple text search (grep/Splunk) by using Large Language Models (LLMs) to understand the context of errors, group them semantically, and provide reasoning for failures.

2. High-Level Architecture

The system follows a Data Lakehouse + RAG (Retrieval Augmented Generation) architecture. It is composed of three distinct layers:

Ingestion & Enrichment Layer (ETL)

Storage Layer (Hybrid)

Intelligence & Application Layer (The Pilot)

Architecture Diagram

```mermaid
graph TD
    subgraph "Smart Ingestion Layer"
        RawLogs[Raw Log Files] --> |File Watcher| TemplateMiner[Template Miner]
        TemplateMiner -- New Pattern? --> SchemaAgent[Schema Discovery Agent (LLM)]
        SchemaAgent -- Define Rules --> RuleStore[Extraction Rules]
        TemplateMiner -- Known Pattern --> Extractor[Fast Feature Extractor]
        RuleStore --> Extractor
        Extractor --> |Standardized + Dynamic Features| Branch{Splitter}
    end

    subgraph "Storage Layer (Hybrid)"
        Branch --> |Metadata & Metrics| TimeSeriesDB[(DuckDB/ClickHouse)]
        Branch --> |Unstructured Context| Vectorizer[Embedding Model]
        Vectorizer --> VectorDB[(ChromaDB/Qdrant)]
    end
```

```mermaid
    subgraph "Security Layer"
        IngestSvc[Ingestion Worker] --> |Raw Log| PIIMasker[PII Masker (Regex)]
        PIIMasker --> |Clean Log| TemplateMiner
    end

    subgraph "Intelligence Layer (LogPilot Agent)"
        User[User Query] --> ChatUI[Chat Interface]
        ChatUI --> Router[Pilot Router / Orchestrator]
        
        Router --> |"Trends / Dashboard"| SQL_Tool[SQL Generator]
        Router --> |"Reasoning / Why"| RAG_Tool[Semantic Search]
        Router --> |"Deep Analysis"| Anomaly_Tool[Pattern Analyzer]
        
        SQL_Tool <--> TimeSeriesDB
        RAG_Tool <--> VectorDB
        
        Router --> Synthesizer[Answer Synthesis]
        Synthesizer --> ChatUI
    end
```


3. The "Standardization" Strategy (Crucial Update)

To handle the variety of logs (DB, App, Firewall) without writing manual parsers for each, we use a Template-Based Extraction approach.

3.1 The Schema Discovery Agent

We cannot run an LLM on every log line (too slow/expensive). Instead, we run it on Log Templates.

Template Mining: The system automatically masks variables.

Raw: User 123 failed login from 192.168.1.1

Template: User <*> failed login from <*>

One-Shot Extraction: If the system sees a new template, it asks the "Schema Agent":

Prompt: "Here is a log template. Extract the interesting technical features as JSON schema."

Agent Output: {"user_id": "index 2", "ip_address": "index 6", "event": "login_failure"}

Fast Application: The system saves this rule. Future logs matching this template are parsed using standard string splitting (very fast), not the LLM.

3.2 Dynamic Schema Evolution

One of the biggest challenges in log management is handling new fields without breaking the schema.

- **The Problem**: A developer adds a new field `latency_ms` to the Payment Service logs.
- **The Old Way**: The ETL pipeline breaks, or we have to manually `ALTER TABLE`.
- **The LogPilot Way**:
    - The `Schema Discovery Agent` detects the new pattern.
    - It maps `latency_ms` to the `context` JSON column automatically.
    - The `Golden Standard` columns remain untouched.
    - **Result**: Zero downtime. The new field is immediately queryable via `context->>'latency_ms'`.

4. The "Golden Standard" Log Schema

Based on industry standards (OpenTelemetry, W3C Common Log Format), we define the following Mandatory Fields that every log must be mapped to during ingestion.

Field Name

Type

Description

Example

timestamp

DATETIME

UTC Timestamp (ISO 8601). Essential for time-series analysis.

2023-10-27T10:00:00Z

severity

STRING

Standardized level. Map legacy levels (e.g., "Crit", "Fatal") to these 5.

- `timestamp`: (DateTime) When it happened.
- `severity`: (String) INFO, ERROR, WARN.
- `service_name`: (String) Who generated it.
- `trace_id`: (String, Optional) For distributed tracing.
- `body`: (String) The **template** (mined), not the raw message.
- `environment`: (String, Optional) prod, staging, dev.
- `app_id`: (String, Optional) Unique application identifier.
- `department`: (String, Optional) Owner department.
- `host`: (String, Optional) Hostname or IP.
- `region`: (String, Optional) Cloud region.
- `context`: (JSON) The dynamic blob containing variable parts (user_id, amount, etc.) and any other metadata.

5. Deep Dive: The "JSON Context" Pattern

You asked how we can query specific questions like "How many failures for User X?" if the database schema is rigid. We use a Hybrid Schema.

The Problem

Payment Logs have transaction_id and amount.

Firewall Logs have src_ip and dest_port.

If we create columns for all of them (amount, src_ip), the table becomes huge and sparse (mostly empty).

The Solution

We store the unique fields in a single JSON column called context.

Visualizing the Database Table

Notice how the context column holds completely different data for different services.

timestamp

service

severity

context (JSON Column)

10:00:01

Payment

ERROR

{"tx_id": "99", "currency": "USD", "error_code": "404"}

10:00:02

Firewall

WARN

{"src_ip": "192.168.1.55", "port": 80, "action": "BLOCK"}

10:00:03

Auth

INFO

{"user_id": "u_admin", "session": "abc", "region": "US-East"}

How the Agent Queries This

When you ask a question, the Agent generates SQL that "looks inside" the JSON.

User Question: "How many failures did User 'u_admin' have?"

Generated SQL (DuckDB/Postgres Style):

SELECT count(*)
FROM logs
WHERE 
  severity = 'ERROR' 
  AND context->>'user_id' = 'u_admin'; -- extracted from JSON on the fly


User Question: "Sum the value of all failed transactions."

Generated SQL:

SELECT sum(CAST(context->>'amount' AS DECIMAL))
FROM logs
WHERE 
  service = 'Payment' 
  AND severity = 'ERROR';


Benefit: We can add a new service tomorrow with completely new fields (e.g., satellite_id) without changing the database structure. The Agent simply learns to query context->>'satellite_id'.

6. Component Detail

6.1 Storage Strategy

Structured DB (DuckDB): Stores the Golden Standards and JSON Context.

Vector DB (ChromaDB): Stores embeddings of the body (message template).

6.2 The Agentic Tools

The Agent needs specialized tools to bridge the gap between "Natural Language" and "Database Rows."

dashboard_generator:

Input: "Show me the error trend for the Payment service last month."

Action: Generates SQL: SELECT date_trunc('day', timestamp), count(*) FROM logs WHERE service='Payment' GROUP BY 1.

Output: A dataset (or chart configuration) ready for visualization.

feature_explorer:

Input: "What user ID is failing the most?"

Action: Scans the JSONB context column. SELECT context->>'user_id', count(*) ...

root_cause_assistant:

Input: "Why are these users failing?"

Action: Vector search on the error messages associated with those User IDs.

7. Next Steps

### Phase 1: The Bootstrap Job (Historical Data)
**Goal**: Ingest 5 years of historical logs to build the initial "Knowledge Base" of templates.

- **Component**: `services/bulk-loader` (Script: `log_loader.py`)
- **Input**: Raw log files in `data/landing_zone/`.
- **Process**:
    1.  **Scan**: Reads files from the landing zone.
    2.  **Parse**: Extracts timestamp, severity, service, and standard metadata (env, app_id, etc.).
    3.  **Mine**: Runs `Drain3` (or mock) to extract templates.
    4.  **Load**: Inserts into DuckDB (`data/logs.duckdb`).
8. Future Phases & Roadmap Extensions

Based on the "Refined Requirements" (docs/refined requirements.md), the following features are designated for future phases to prioritize the core MVP.

## 5. Interface Layer (API Gateway)

The **API Gateway** (`services/api_gateway`) serves as the single entry point for all external interactions.
- **Technology**: FastAPI + Uvicorn.
- **Endpoints**: `POST /query` (Natural Language Interface).
- **Integration**: Direct invocation of the Pilot Orchestrator's LangGraph.

## 6. Evaluation & Optimization

The **Evaluator Service** (`services/evaluator`) ensures reliability and performance.
- **Golden Datasets**: Curated examples for Schema Discovery, SQL Generation, and RAG.
- **Scoring**: Automated metrics (Regex Match, SQL Execution Match, Semantic Similarity).
- **Benchmarking**: CLI tools to compare different LLM models and prompts.
(`POST /chat`), log ingestion (`POST /logs`), and system health (`GET /health`).
- **Authentication**: Validates API keys or JWT tokens.
- **Documentation**: Auto-generates Swagger/OpenAPI docs for easy integration.

### Why API-First?
- **Flexibility**: Can be consumed by a CLI, a Web Dashboard (React/Vue), or a Chatbot (Slack/Discord).
- **Decoupling**: Separates the "Brain" (Orchestrator) from the "Mouth" (Interface).

8.2 Predictive Analytics (Phase 3)
- **Requirement**: Predict system issues (bottlenecks, degradation) before they occur.
- **Architecture Add-on**:
    - **Forecasting Service**: A new microservice running time-series models (Prophet, ARIMA, or LSTM).
    - **Input**: Aggregated metrics from DuckDB (e.g., error_rate per hour).
    - **Output**: "Risk Scores" written back to DuckDB for the Agent to query.

8.3 Workflow Integrations (Phase 3)
- **Requirement**: Connect AI outputs to Jira/ServiceNow.
- **Architecture Add-on**:
    - **Action Tools**: New tools for the `tool-service` (e.g., `jira_ticket_creator`, `slack_notifier`).
    - **Approval Flow**: The Agent will propose an action ("Shall I create a ticket?"), and the user must approve via the Chat UI before the tool executes.

8.3 Real-Time vs. Near Real-Time
- **Optimization**: For sub-second latency requirements in the future, we can switch the Ingestion Worker to a streaming engine (e.g., Flink or Spark Streaming) without changing the downstream Query Layer.

9. Enterprise Readiness & Non-Functional Requirements

To ensure LogPilot meets enterprise standards, we incorporate the following architectural pillars:

9.1 Security & Access Control
- **RBAC (Role-Based Access Control)**:
    - **Admin**: Full access to system config and all logs.
    - **Analyst**: Read-only access to logs and dashboards.
    - **Viewer**: Restricted access (e.g., can only see logs for their specific `department`).
- **Encryption**:
    - **At Rest**: All DuckDB files and Vector indices are encrypted using AES-256.
    - **In Transit**: All internal service communication (gRPC/REST) and user traffic uses TLS 1.3.
- **Audit Trails**:
    - Every user query ("Show me errors...") is itself logged to a separate `audit_logs` table for compliance review.

9.2 Data Lifecycle Management (Tiered Storage)
To balance performance and cost, we use a tiered storage strategy:
- **Hot Tier (DuckDB)**:
    - **Retention**: 30 Days.
    - **Storage**: High-speed NVMe SSD.
    - **Use Case**: Real-time debugging, recent trend analysis.
- **Warm Tier (Parquet/S3)**:
    - **Retention**: 1 Year.
    - **Storage**: S3 Standard / GCS.
    - **Use Case**: Monthly reporting, deep historical analysis.
- **Cold Tier (Glacier/Archive)**:
    - **Retention**: 5-7 Years (Compliance).
    - **Storage**: S3 Glacier.
    - **Use Case**: Legal hold, regulatory audits.
- **Lifecycle Manager**: A background service automatically moves data between tiers based on timestamp.

9.3 Compliance & Privacy
- **PII Masking**:
    - The `Ingestion Worker` automatically detects and hashes sensitive data (Credit Cards, SSNs) *before* it hits the database.
- **Right to be Forgotten**:
    - Supported via the `user_id` key in the `context` column. A "Purge Job" can delete all records associated with a specific user ID across all tiers.

9.4 End-to-End Data Flow (with Security)

```mermaid
graph LR
    Raw[Raw Log Stream] --> Ingest[Ingestion Worker]
    Ingest --> PII[PII Masker (shared/utils.py)]
    PII --> |Cleaned| Miner[Template Miner]
    Miner --> |Template| Registry[Schema Registry]
    Registry --> |Schema| DB[(DuckDB)]
    
    style PII fill:#f9f,stroke:#333,stroke-width:2px
```

10. High Availability (HA) & Scalability
- **Ingestion Layer**:
    - The `Ingestion Worker` is stateless and can scale horizontally (K8s ReplicaSet) to handle 10TB+/day.
    - Kafka acts as the backpressure buffer.
- **Query Layer**:
    - **Read Replicas**: We can spin up multiple read-only DuckDB instances pointing to the same underlying storage (or replicated storage) to handle high concurrent user queries.
- **API Gateway**:
    - Load balanced behind an Nginx/Cloud Load Balancer.

11. System Catalog Integration (Unified Data Layer)
To answer business-centric questions (e.g., "Which department has the most errors?"), we integrate a **System Catalog** directly into the structured storage.

- **Source**: `data/system_catalog.csv` (System Name, Department, Owner, Criticality).
- **Mechanism**: Loaded into DuckDB as the `system_catalog` table.
- **Relationship**: **Many-to-Many**. A single service (e.g., `auth-service`) can belong to multiple departments (e.g., `Security` and `Finance`).
- **Usage**: The Agent uses SQL `JOIN` operations.
    - *Impact Analysis*: "Show all departments affected by auth-service errors" -> Returns both Security and Finance.
    - *Note*: Aggregating errors by Department will count the same error multiple times (once per department). This is intentional for impact assessment.

12. Design History & References
Detailed design documents for specific components have been archived for reference:

- **[Agent Design](design_history/agent_design.md)**: Deep dive into LangGraph state machine.
- **[Testing Strategy](design_history/testing_strategy.md)**: Unit, Integration, and E2E testing standards.
- **[Data Sources](design_history/data_sources.md)**: Explanation of the "Single Input, Dual View" philosophy.
- **[Schema Discovery](design_history/schema_discovery_deep_dive.md)**: Analysis of the regex generation loop.
- **[Workflow Diagrams](design_history/workflow.md)**: Detailed ASCII and Mermaid data flow diagrams.