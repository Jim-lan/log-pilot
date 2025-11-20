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

DEBUG, INFO, WARN, ERROR, FATAL

service_name

STRING

The system or microservice generating the log.

PaymentGateway, AuthService, PostgresDB

trace_id

STRING

(Optional) Distributed tracing ID to correlate across services.

a1b2c3d4e5

body

STRING

The Template or sanitized message (PII removed).

User <User> failed login

context

JSON

The "Catch-All" bucket for all specific features.

{"user_id": "u1", "ip": "10.0.0.1"}

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

Ingestion Script: We will write a Python script to read your raw logs.

Apply Standards: The script will map your specific log format to the Golden Standard table structure defined in Section 4.

Load DB: We will insert these mapped records into a local DuckDB instance to prove the "JSON Context" querying works.