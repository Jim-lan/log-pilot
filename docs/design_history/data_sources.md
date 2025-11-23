# 📊 Data Sources & Flow: Single Input, Dual View

## 1. The Single Source of Truth
You are correct. The **only** raw input to LogPilot is the **Log Stream** (files or Kafka topics).
We do not connect to external databases, metrics stores, or documentation wikis. Everything the agent knows comes from the logs you feed it.

## 2. One Input, Two Destinations
While the input is single (Logs), we split it into two internal "brains" to handle different types of questions.

### Input: Raw Log Stream
```text
2025-11-20 10:00:01 INFO payment-service: Payment processed for user_id=101
```

### Destination A: The "Left Brain" (Structured Data)
*   **Storage**: DuckDB (`logs` table)
*   **Purpose**: Exact math, counting, grouping, time-series.
*   **Used By**: `SQLGenerator`
*   **Example Query**: "Count error rate per hour."
*   **Schema**:
    *   `timestamp` (DateTime)
    *   `service_name` (String)
    *   `severity` (String)
    *   `body_template` (String - from Drain3)
    *   `context` (JSON)

### Destination B: The "Right Brain" (Knowledge Base)
*   **Storage**: ChromaDB (Vector Store)
*   **Purpose**: Understanding meaning, finding similar errors, explaining "why".
*   **Used By**: `RAGRetriever`
*   **Example Query**: "Why did the payment fail?"
*   **Content**:
    *   Embeddings of log messages.
    *   Embeddings of *templates* (to save space).

## 3. The Flow
1.  **Ingestion Worker**: Reads the Raw Log.
2.  **Parser**: Extracts timestamp/service (Regex).
3.  **Miner**: Extracts the Template (Drain3).
4.  **Router**:
    *   --> **DuckDB**: Inserts the structured row immediately.
    *   --> **Knowledge Base**: (Async) Embeds the log/template for semantic search.

## 4. Why this matters?
By relying *only* on logs, LogPilot is:
*   **Self-Contained**: No complex integrations needed.
*   **Truthful**: It doesn't hallucinate based on outdated wiki docs; it only knows what the system *actually* reported.
