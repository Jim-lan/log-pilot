# Detailed Architecture 🏗️

## 1. Component Diagram

The LogPilot system consists of 5 main containerized services:

```mermaid
graph TD
    User[User] <--> Frontend[Frontend (Nginx)]
    Frontend <--> |REST API| Pilot[Pilot Orchestrator (FastAPI)]
    
    subgraph "Data Layer"
        Pilot <--> |Read-Only| LogsDB[(logs.duckdb)]
        Pilot <--> |Read-Write| HistoryDB[(history.duckdb)]
        Pilot <--> |Read-Only| VectorDB[(ChromaDB)]
    end
    
    subgraph "Ingestion Layer"
        LogFiles[Log Files] --> |Watch| Worker[Ingestion Worker]
        Worker --> |Write| LogsDB
        Worker --> |Embed| VectorDB
    end
    
    subgraph "Intelligence Layer"
        Pilot <--> |HTTP| LLM[LLM Service (Ollama)]
    end
```

## 2. Sequence Diagrams

### A. User Query Flow (End-to-End)

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as Pilot API
    participant G as Graph (LangGraph)
    participant DB as DuckDB
    participant LLM as Ollama

    U->>FE: "Show last 5 errors"
    FE->>API: POST /query
    API->>G: invoke(query)
    
    G->>LLM: Rewrite Query
    LLM-->>G: "SELECT * FROM logs..." (or natural language)
    
    G->>LLM: Classify Intent
    LLM-->>G: "sql"
    
    G->>LLM: Generate SQL
    LLM-->>G: "SELECT * FROM logs..."
    
    G->>G: Validate SQL (Guardrails)
    
    G->>DB: Execute SQL
    DB-->>G: Result Rows
    
    G->>LLM: Synthesize Answer
    LLM-->>G: Final Answer
    
    G-->>API: Final State
    API-->>FE: JSON Response
    FE-->>U: Display Answer
```

### B. Ingestion Flow

```mermaid
sequenceDiagram
    participant File as Log File
    participant Watcher as File Watcher
    participant PII as PII Masker
    participant DB as DuckDB
    participant Chroma as ChromaDB

    File->>Watcher: New Line Appended
    Watcher->>PII: Send Raw Line
    PII->>PII: Mask Emails/IPs
    PII->>DB: Insert into 'logs' table
    
    opt If Runbook/Doc
        PII->>Chroma: Embed & Store
    end
```

## 3. Service Details

### Pilot Orchestrator
-   **Framework**: FastAPI + LangGraph.
-   **Role**: Manages the cognitive architecture (Rewrite -> Plan -> Execute -> Verify).
-   **State Management**: Uses `langgraph` StateGraph to pass context between nodes.

### Ingestion Worker
-   **Role**: Real-time log processing.
-   **Mechanism**: Uses `watchdog` to monitor file system events.
-   **PII Masking**: Regex-based masking for emails, IP addresses, and SSNs before storage.

### Database Layer
-   **DuckDB**: Chosen for high-performance OLAP queries on local files.
-   **ChromaDB**: Vector store for RAG (Retrieval Augmented Generation).
