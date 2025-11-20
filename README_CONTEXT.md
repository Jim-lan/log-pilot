LogPilot: Project Master Context & Implementation Guide

1. Project Overview & Vision

GenAI LogPilot is an enterprise-grade log analytics platform designed to ingest, understand, and query massive volumes of heterogeneous system logs.

Unlike traditional tools (Splunk/ELK) that rely on keyword search, LogPilot uses a "Dual-Brain" approach:

SQL Intelligence (DuckDB): Answers quantitative questions ("How many errors in May?", "Which department failed most?").

Vector Intelligence (RAG): Answers qualitative questions ("Why is the checkout failing?", "What is the root cause pattern?").

2. Functional Requirements (derived from Design Discussions)

A. The User Queries

The system must support two distinct types of user intent:

Reporting/Dashboarding: "Generate a dashboard for 2024," "Show failure trends by Service."

Reasoning/Deep Dive: "What is the abnormal pattern here?", "Why did this specific user fail?"

B. Data Handling

Heterogeneity: The system must handle diverse logs (Firewall, App, DB) without rigid database schemas.

Scale: It must support Historical Data (5 years of archives) and Real-Time Data (Streaming).

Standardization: Raw logs must be "enriched" into a standard format before analysis.

3. Core Architectural Decisions

Decision #1: The "Hybrid" Storage Strategy

Decision: We will NOT put all logs into a Vector DB (too expensive/slow).

Implementation:

DuckDB: Stores 100% of logs (Metadata + Metrics + JSON Context).

ChromaDB: Stores only unique Log Templates (Embeddings).

Decision #2: Template Mining (The "Standardization" Layer)

Context: Discussed how to handle millions of raw text lines.

Strategy: Use Drain3 (or similar clustering) to convert raw logs into Templates (e.g., User <*> failed login).

Benefit: We only embed the Template once, not the 1 million occurrences.

Decision #3: The "Golden Standard" & "JSON Context"

Context: Discussed how to extract features from different log types (Payment vs. Firewall).

Strategy:

Golden Fields (Columns): timestamp, severity, service_name, trace_id, body (template).

Context (JSON Column): A flexible JSON blob storing dynamic fields (e.g., {"tx_id": "99", "src_ip": "10.0.0.1"}).

Querying: The SQL Agent will generate queries using JSON extraction syntax (e.g., context->>'tx_id').

4. Microservices Design (The "Dual Pipeline")

We use a Phased Implementation to handle Historical vs. Real-Time loads.

Phase 1: The Bootstrap Job (History)

Type: Ephemeral Kubernetes Job.

Task: Reads 5 years of archives -> Mines Templates -> Writes Parquet Files -> Bulk Loads DuckDB.

Output: A populated DB and a "Schema Registry" of known Regex patterns.

Phase 2: The Ingestion Service (Real-Time)

Type: Always-on Daemon.

Task: Consumes Kafka -> Checks Schema Registry -> Inserts to DB.

Handover: Starts consuming Kafka from the timestamp where Phase 1 finished.

5. Mandatory Folder Structure

The Agent must generate the project using this exact structure:

log-pilot/
├── docs/                           # Design Documents
│   ├── architecture.md             # (To be populated from Chat History)
│   └── microservices.md            # (To be populated from Chat History)
│
├── infrastructure/                 # Infrastructure as Code
│   ├── docker-compose.yml          # Kafka, DuckDB, Chroma (Local Dev)
│   └── k8s/                        # Kubernetes manifests
│
├── shared/                         # Shared Logic (Used by both Loader & Worker)
│   ├── log_schema.py               # Defines the Golden Standard Class
│   └── db_connectors.py            # Wrappers for DuckDB/Chroma
│
├── services/                       # Microservices Source Code
│   │
│   ├── ingestion-worker/           # Phase 2 Service (Real-Time)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── main.py             # Main Entrypoint
│   │
│   ├── bulk-loader/                # Phase 1 Job (History)
│   │   ├── Dockerfile
│   │   └── src/
│   │       └── job.py
│   │
│   ├── schema-registry/            # Service 4: Regex Rule Manager
│   │   └── src/
│   │       └── api.py
│   │
│   ├── pilot-orchestrator/         # Service 6: The AI Brain
│   │   ├── Dockerfile
│   │   └── src/
│   │       └── agent.py            # LangChain Orchestrator
│   │
│   └── tool-service/               # Service 7: SQL & RAG Tools
│       └── src/
│           ├── sql_gen.py
│           └── rag_retriever.py
│
└── scripts/
    └── init_dev_env.sh


6. Implementation Roadmap (Immediate Next Steps)

Scaffold: Generate the folder structure above.

Shared Lib: Implement shared/log_schema.py to define the Data Class for the Golden Standard.

Ingestion Prototype: Implement services/ingestion-worker/src/main.py using the logic defined in the design session (Mocking Drain3 and Kafka for now).