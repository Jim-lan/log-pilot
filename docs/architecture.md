# Detailed Architecture 🏗️

## 1. Component Diagram

The LogPilot system consists of 6 main containerized services:

```mermaid
graph TD
    User[User] <--> Frontend["Frontend (Nginx)"]
    Frontend <--> |REST API| Pilot["Pilot Orchestrator (FastAPI)"]
    
    subgraph "Data Layer"
        Pilot <--> |Read-Only| LogsDB[(logs.duckdb)]
        Pilot <--> |Read-Write| HistoryDB[(history.duckdb)]
        Pilot <--> |Read-Only| VectorDB[(ChromaDB)]
    end
    
    subgraph "Ingestion Layer"
        Generator[Log Generator] --> |Generates| LandingZone[Landing Zone Folder]
        LandingZone --> |Watch| Worker[Ingestion Worker]
        Worker --> |Write| LogsDB
        Worker --> |Embed| VectorDB
    end
    
    subgraph "Intelligence Layer"
        Pilot <--> |HTTP| LLM["LLM Service (Ollama)"]
    end

    subgraph "Evaluation Layer"
        Eval[Evaluation Service] <--> |Batch| Pilot
        Eval <--> |Judge| LLM
        Eval --> |Store| MetricsDB[(metrics.duckdb)]
    end
```

## 2. Sequence Diagrams

### A. User Query Flow (Agentic RAG)

```mermaid
sequenceDiagram
    participant U as User
    participant API as Pilot API
    participant G as Graph (LangGraph)
    participant LLM as Ollama
    participant DB as DuckDB

    U->>API: "How do I fix error 503?"
    API->>G: invoke(query)
    
    G->>LLM: Rewrite Query (Context)
    LLM-->>G: "How do I fix error 503 in auth-service?"
    
    G->>LLM: Classify Intent
    LLM-->>G: "rag"
    
    loop Context Verification
        G->>DB: Retrieve Logs/Docs
        G->>LLM: Verify Context Relevance
        alt Context Invalid
            G->>G: Rewrite Query / Retry
        else Context Valid
            G->>G: Proceed
        end
    end
    
    loop Answer Validation
        G->>LLM: Synthesize Answer
        G->>LLM: Validate Answer vs Intent
        alt Answer Invalid (Lazy/Hallucination)
            G->>G: Retry with Feedback
        else Answer Valid
            G->>G: Proceed
        end
    end
    
    G-->>API: Final Answer
    API-->>U: Display Answer
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

## 3. Detailed Request Workflow (The Brain) 🧠

LogPilot uses **LangGraph** to orchestrate a team of specialized agents. The flow is not linear; it loops and self-corrects based on validation feedback.

### A. The Cognitive Flow
```mermaid
stateDiagram-v2
    state "User Sends Query" as Start
    state "Send Final Answer" as End

    Start --> Rewrite
    Rewrite --> Classify
    
    state Classify_Decision <<choice>>
    Classify --> Classify_Decision
    
    Classify_Decision --> SQL_Gen: Intent = SQL
    Classify_Decision --> RAG_Retrieve: Intent = RAG
    Classify_Decision --> Synthesize: Intent = Ambiguous

    state "SQL Loop" as SQL_Loop {
        SQL_Gen --> Validate_SQL
        Validate_SQL --> Execute_SQL: Valid
        Validate_SQL --> Fix_SQL: Invalid
        Fix_SQL --> Validate_SQL
    }
    
    state "RAG Loop" as RAG_Loop {
        RAG_Retrieve --> Verify_Context
        Verify_Context --> Synthesize: Valid
        Verify_Context --> Rewrite: Invalid (Feedback)
    }

    Execute_SQL --> Synthesize
    
    Synthesize --> Validate_Answer
    Validate_Answer --> End: Valid
    Validate_Answer --> Synthesize: Invalid (Retry)
```

### B. Agent Inventory
The system is composed of **10 distinct Nodes (Agents)**, each with a specific responsibility. "LLM" indicates a creative AI step, while "Code" indicates deterministic logic.

| Agent Name | Role | Type | Responsibility |
| :--- | :--- | :--- | :--- |
| **1. Query Rewriter** | `rewrite_query` | 🤖 LLM | Transforms raw user input (e.g., "what about errors?") into a standalone, context-aware query using chat history. |
| **2. Intent Router** | `classify_intent` | 🤖 LLM (CoT) | **Chain of Thought**: Analyzes if query needs *Data* (SQL) or *Knowledge* (RAG) before deciding. Prevents "404=Duration" hallucinations. |
| **3. SQL Expert** | `generate_sql` | 🤖 LLM | Translates natural language into dialect-specific SQL (DuckDB). Enforces syntax rules. |
| **4. SQL Critic** | `validate_sql` | ⚙️ Code | Deterministic validation. Checks for syntax (`EXPLAIN`) and **Schema Columns** (injects valid columns on error). |
| **5. Repair Agent** | `fix_sql` | 🤖 LLM | Receives error logs from the Critic and attempts to fix the SQL syntax. |
| **6. Tool Executor** | `execute_sql` | ⚙️ Code | Runs the valid SQL against `logs.duckdb` and captures the result (or runtime error). |
| **7. RAG Retriever** | `retrieve_context` | ⚙️ Code | Queries `ChromaDB` for patterns, then fetches matching full logs from DuckDB. |
| **8. Context Critic** | `verify_context` | 🤖 LLM | **Strict Verification**: Enforces that if a specific Error Code is queried, the retrieved context *must* contain it. |
| **9. Answer Synthesize** | `synthesize_answer` | 🤖 LLM | Combines the User Query + Data/Context into a helpful, human-readable response. |
| **10. QA Critic** | `validate_answer` | 🤖 LLM | Final check. Ensures the answer is not "lazy" (e.g., "I don't know") if data was actually found. |

## 4. Service Details

### Pilot Orchestrator
-   **Framework**: FastAPI + LangGraph.
-   **Role**: Manages the cognitive architecture (Rewrite -> Plan -> Execute -> Verify).
-   **State Management**: Uses `langgraph` StateGraph to pass context between nodes.
-   **Agentic Features**: Self-correction loops for Context and Answer verification.

### Log Generator (Demo Data Source)
-   **Role**: Creates a realistic 12-month historical dataset on startup.
-   **Function**: Simulates 4 services (Payment, Auth, DB, Frontend) with random anomalies.
-   **Output**: Writes logs to `data/source/landing_zone`, then exits.

### Ingestion Worker
-   **Role**: Real-time log processing.
-   **Mechanism**:
    -   **File Watcher**: Uses `watchdog` to listen for new files in `landing_zone`.
    -   **Processing**: Automatically ingests files and moves them to `processed/`.
-   **PII Masking**: Regex-based masking for emails, IP addresses, and SSNs before storage.

### Evaluation Service (New)
-   **Role**: Offline performance measurement.
-   **Stack**: FastAPI + Ragas.
-   **Function**: Runs the `golden_dataset.json` against the Pilot and scores results using an LLM Judge.

### Database Layer
-   **DuckDB**: Chosen for high-performance OLAP queries on local files.
-   **ChromaDB**: Vector store for RAG (Retrieval Augmented Generation).

## 5. Agentic RAG Logic & Fallback Strategy 🧠

The **RAG (Retrieval Augmented Generation)** pipeline is designed for **qualitative** questions—when you need to know "Why", "How", or "Who", rather than "How many".

### A. The Trigger Logic
The **Intent Router** selects the `rag` path when the query implies causality, identity, or procedure.
*   **Keywords**: "Why", "How to", "Who owns", "Runbook".
*   **Examples**:
    *   *"Why is the payment service failing?"* (RAG 🟢)
    *   *"Count errors in the last hour."* (SQL 🔴)

### B. The Logic Pipeline (Hybrid Search)
If RAG is selected, we execute a specialized 3-step process:

1.  **Semantic Pattern Match (ChromaDB)**:
    *   We embed the query to find abstract **Log Patterns** (e.g., `Payment gateway timed out after <*> ms`).
    *   We do *not* search raw logs directly, which ensures we find the *type* of error even if the specific timestamp/user ID is different.

2.  **Structured Data Fetch (DuckDB)**:
    *   We extract the `template_id` from the matched pattern.
    *   We query **DuckDB** for the *actual* recent logs that match that ID to get real timestamps and values.

3.  **Context Verification (The Critic)**:
    *   An LLM Critic reads the fetched logs.
    *   **Logic**: "Does this log actually answer the user's question?"
    *   **Strict Rule**: If the user asks for "Error 502", the system *must* have found 502.
    *   **Window Retrieval**: If a match is found, we fetch the surrounding **+/- 30s** of logs to provide causal context (e.g., Timeout -> Error) to the LLM.

### C. The Fallback (Web Search) 🌍
If the RAG pipeline fails (e.g., no patterns found, or Critic rejects them), the system triggers a **Web Search**:
1.  **Condition**: User asks a general question ("What is error 503?") OR internal logs are irrelevant.
2.  **Action**: The `perform_web_search` node queries DuckDuckGo.
3.  **Result**: The system answers using external documentation instead of internal logs.

### D. Decision Flowchart
```mermaid
graph TD
    Q[User Query] --> Router{Intent?}
    Router -- "Count/Start/List" --> SQL[SQL Agent]
    Router -- "Why/How/Who" --> RAG[RAG Agent]
    
    subgraph RAG Logic
        RAG --> Chroma[1. Pattern Match]
        Chroma --> DuckDB[2. Fetch Logs]
        DuckDB --> Critic{Relevant?}
        Critic -- Yes --> Answer[Final Answer]
        Critic -- No --> Web[3. Web Fallback]
    end
```

## 6. Smart Runbook Ingestion (The Reader Agent) 🧠📘

While `drain3` handles structured logs, **Technical Runbooks** (Markdown/PDF) require a different approach. We employ an **AI Reader Agent** to de-fragment and ingest this static knowledge.

### A. The Problem: "Fragmented Knowledge"
A runbook often mentions "Error 503" in multiple places:
1.  **Table of Contents**: Lists it.
2.  **Symptoms Section**: Describes what it looks like.
3.  **Fix Section**: Describes how to solve it.

Standard **Chunking** (splitting text by 500 characters) fails here. It creates 3 separate, incomplete vectors. If you search "How to fix 503", you might get the symptoms card but not the fix card.

### B. The Solution: "Smart Synthesis"
The **Ingestion Worker** uses a 2-Pass LLM Strategy:

1.  **Pass 1: Discovery (The Scanner)**
    *   The Agent scans the document to identify **Key Topics** (e.g., `["Error 503", "Auth Token Expired"]`).
    *   **New**: It specifically looks for topics inside **Tables** and **Headers** to ensure no error code is missed (e.g., `| 502 | Bad Gateway |`).
    *   It ignores generic text.

2.  **Pass 2: Synthesis (The Researcher)**
    *   For *each* topic, the Agent re-reads the *entire* document.
    *   It extracts all relevant clauses (Symptoms + Cause + Fix) from scattered sections.
    *   It synthesizes a **Single Knowledge Card**.

### C. The Result: "High-Quality Vectors"
The Vector DB stores the **Synthesized Card**, not the raw text.
*   **Query**: "How to fix 503?"
*   **Retrieved Vector**: A complete mini-guide containing the definition AND the fix.
*   **Outcome**: The RAG Agent answers correctly with full context.

## 7. Storage Optimization Strategy

The current architecture prioritizes **simplicity and context** for the LLM by storing full log bodies. However, for high-volume production environments, a **Log Normalization** strategy is designed and feasible.

### Option A: Full Log Storage (Current)
-   **Schema**: `timestamp`, `service`, `severity`, `body` (full text), `template_id`.
-   **Pros**: Zero reconstruction cost, easy debugging, full-text search.
-   **Cons**: Higher storage footprint (redundant text).
-   **Best For**: AI Agents (needs exact context), <1TB scale.

### Option B: Normalized Storage (Future Optimization)
-   **Schema**: `timestamp`, `service`, `severity`, `template_id`, `parameters` (JSON list).
-   **Mechanism**:
    1.  `LogTemplateMiner` extracts template (e.g., "User <*> failed") and parameters (e.g., `["bob"]`).
    2.  Store only the parameters in DuckDB.
    3.  Reconstruct log message dynamically for display or LLM context.
-   **Pros**: Minimal storage (up to 90% reduction for repetitive logs), efficient analytics on parameters.
-   **Cons**: Reconstruction overhead, complexity in search (cannot grep raw text).
-   **Feasibility**: Verified via `tests/check_drain3.py` that `drain3` supports parameter extraction.

## 8. Vector DB Usage Scenarios

The Vector DB (ChromaDB) is the "Semantic Brain" of LogPilot. It is used when the user's question is **vague, qualitative, or pattern-based**.

### Example 1: Semantic Discovery ("What's wrong?")
*   **User Query**: *"Are there any authentication issues?"*
*   **Why Vector DB?**: The word "issues" is subjective. SQL can't query `WHERE body LIKE '%issue%'` effectively.
*   **The Flow**:
    1.  **Embed**: Convert query to vector.
    2.  **Search**: Find patterns near "authentication" and "error/fail".
    3.  **Match**: ChromaDB returns pattern `User <*> failed to login`.
    4.  **Retrieve**: System uses the pattern's `template_id` to fetch recent logs from DuckDB.
    5.  **Answer**: "Yes, I found a recurring pattern of login failures..."

### Example 2: Pattern Matching ("Find logs like this")
*   **User Query**: *"Show me logs similar to the database timeout."*
*   **Why Vector DB?**: "Similar to" is a vector operation.
*   **The Flow**:
    1.  **Search**: ChromaDB finds the `Database connection timed out after <*> ms` pattern.
    2.  **Retrieve**: Uses `template_id` to get specific instances.

### Example 3: When is it NOT used? (Pure SQL)
*   **User Query**: *"Count the number of errors in the last hour."*
*   **Why NOT Vector DB?**: This is a precise, quantitative question.
*   **The Flow**:
    1.  **Intent Classifier**: Detects "SQL" intent.
    2.  **Generate SQL**: `SELECT count(*) FROM logs WHERE severity='ERROR' AND timestamp > now() - INTERVAL 1 HOUR`.
    3.  **Execute**: Runs directly on DuckDB. Vector DB is bypassed completely.

## 9. Production Data Architecture: Stateless on S3

In our current **Demo/MVP** environment, we ingest logs into a local DuckDB file (`logs.duckdb`). In a **Real-World Production** environment, we recommend a **Stateless Architecture** that queries data directly where it lives (e.g., S3), avoiding data duplication.

### A. Current Approach (Local Storage)
*   **Mechanism**: Ingestion Worker reads logs -> Inserts into local `logs.duckdb` file.
*   **Pros**: Extremely fast for small/medium datasets, simple setup, no network latency.
*   **Cons**: Data duplication (logs exist in file & DB), limited by local disk, stateful (harder to scale horizontally).

### B. Production Approach (Stateless on S3)
*   **Concept**: Treat S3 as the database. DuckDB acts as a **stateless compute engine** that queries Parquet files directly on S3.
*   **Mechanism**:
    1.  **Log Storage**: Logs are shipped to S3 in Parquet format (e.g., via Kinesis Firehose or FluentBit).
    2.  **Compute**: LogPilot spins up a DuckDB instance (in Lambda or Container) only when a query is needed.
    3.  **Query**: `SELECT * FROM 's3://my-log-bucket/date=2024-01-01/*.parquet'`.
*   **Pros**:
    *   **Zero Data Movement**: No need to "ingest" or move data into a separate DB.
    *   **Infinite Scale**: S3 handles the storage; DuckDB handles the compute.
    *   **Cost Effective**: Pay only for S3 storage and query compute time.

### How to Achieve This
To transition LogPilot to this architecture:

1.  **Install Extensions**:
    ```sql
    INSTALL httpfs;
    LOAD httpfs;
    INSTALL aws;
    LOAD aws;
    ```

2.  **Configure Credentials**:
    ```python
    con.execute("CALL load_aws_credentials()")
    ```

3.  **Query Directly**:
    ```python
    # Instead of querying a local table 'logs'
    sql = "SELECT count(*) FROM read_parquet('s3://company-logs/service-a/*.parquet')"
    con.execute(sql)
    ```

This allows LogPilot to become a **Zero-ETL** agent, providing intelligence on top of your existing Data Lake.

## 10. Cloud-Native Adaptation: AWS CloudWatch ☁️

For environments where logs are stored in **AWS CloudWatch Logs** (e.g., AWS Glue jobs), we can adapt LogPilot to query them directly without ingestion, acting as a smart UI over the CloudWatch API.

### Architecture Changes
To support the "Live CloudWatch Log Access" pattern, we swap specific components while keeping the core cognitive architecture:

| Component | Current (DuckDB) | Cloud-Native (CloudWatch) |
| :--- | :--- | :--- |
| **Intent Router** | `classify_intent` (Same) | `classify_intent` (Same) |
| **Generator** | `SQLGenerator` (DuckDB SQL) | **`InsightsGenerator`** (CloudWatch Syntax) |
| **Executor** | `DuckDBConnector` | **`CloudWatchConnector`** (Boto3) |
| **Vector DB** | Ingests all patterns | **Pattern Sampler** (Ingests patterns from samples) |

### Implementation Strategy

#### 1. Insights Generator (The "Translator")
We create a new prompt in `PromptFactory` to translate natural language into CloudWatch Insights syntax.

**Prompt Template**:
```text
You are an AWS CloudWatch Expert.
Translate the user question: "{query}"
Into CloudWatch Logs Insights syntax.

Example:
Q: "Show me the last 20 errors"
A: fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20
```

#### 2. CloudWatch Connector (The "Executor")
#### 2. CloudWatch Connector (The "Executor")
We implement a connector using the **AWS SDK (Boto3)** to execute the generated query. This connector is responsible for:
1.  **Initiating Queries**: Sending the `start_query` request to the CloudWatch Logs API.
2.  **Polling**: Waiting for the asynchronous query execution to complete.
3.  **Result Parsing**: Converting the JSON response from CloudWatch into a structured format for the LLM.

#### 3. Smart RAG Fallback
If the user asks a qualitative question ("Why did the job fail?"), we use a **Hybrid Flow**:
1.  **Retrieve**: Fetch recent error logs via CloudWatch Insights (`filter @message like /ERROR/`).
2.  **Pattern**: Run `LogTemplateMiner` on the *retrieved results* in-memory.
3.  **Augment**: Feed the unique patterns + sample errors into the LLM to synthesize an answer.

This approach achieves **Zero Data Duplication** while leveraging LogPilot's agentic capabilities.

## 11. Design Considerations & Trade-offs ⚖️

This section summarizes the key architectural decisions to help stakeholders understand "Why" we built it this way.

### A. Why DuckDB + ChromaDB? (The Hybrid Engine)
*   **The Problem**: Vector DBs are great for "vague" questions but terrible for "precise math" (e.g., "Count errors"). SQL DBs are the opposite.
*   **The Solution**: We use **Both**.
    *   **DuckDB**: Handles the "Hard Math" (Counting, Aggregation, Filtering).
    *   **ChromaDB**: Handles the "Soft Logic" (Pattern matching, Similarity).
*   **Business Value**: You get the accuracy of a SQL report with the flexibility of ChatGPT.

### B. Why "1 Vector Per Pattern"?
*   **The Problem**: Storing every single log line as a vector is expensive and slow (100M logs = 100M vectors).
*   **The Solution**: We only store **Unique Patterns** (e.g., 1 vector for "User <*> failed").
*   **Business Value**:
    *   **99% Cost Reduction**: A system with 100M logs might only have 500 unique patterns.
    *   **Faster Answers**: Searching 500 vectors is instant.

### C. Why "Zero-ETL" for Production? (S3/CloudWatch)
*   **The Problem**: Moving data from S3/CloudWatch to another DB costs money (egress) and time (latency).
*   **The Solution**: Bring the compute to the data.
    *   **Stateless DuckDB**: Queries S3 Parquet files directly.
    *   **CloudWatch Connector**: Queries AWS Logs directly.
*   **Business Value**:
    *   **Real-Time**: No waiting for ingestion pipelines.
    *   **Cost Savings**: No duplicate storage costs.
    *   **Simplicity**: Fewer moving parts to maintain.

## 12. Future Roadmap & Risks 🔮
For a detailed breakdown of architectural risks (e.g., Latency, Context Limits) and planned enhancements (S3, CloudWatch Support), please refer to the **[Project Backlog](backlog.md)**.
