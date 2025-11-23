# 🏗️ Design: System Catalog Integration

## 1. The Goal
We want to answer "Business Questions" about our logs.
*   *Input*: "Which **department** has the most errors?"
*   *Data*:
    *   **Logs**: `service_name`, `error_count` (in DuckDB/Chroma).
    *   **Catalog**: `service_name` <-> `department` (New Source).

## 2. Evaluation of `SQLAutoVectorQueryEngine`
You asked about using LlamaIndex's `SQLAutoVectorQueryEngine`.

### What it is
It is a tool that decides whether to route a query to a **SQL Database** OR a **Vector Store**, or **Both** (using Auto-Retrieval).

### Pros
*   **Automation**: Handles the "Router" logic for you.
*   **Hybrid**: Can filter vector search using SQL metadata (if set up correctly).

### Cons (For our Architecture)
*   **Black Box**: It hides the logic. In LogPilot, we use **LangGraph** as our "Brain" to make these decisions explicitly.
*   **Join Difficulty**: It is not designed to "Join" data across two different systems easily. It usually assumes one view.
*   **Overkill**: We already have a Router (The Pilot Orchestrator).

## 3. Recommended Design: The "Unified Data Layer"
Instead of treating the Catalog as a separate "Tool" that the agent has to query and then manually correlate, we should **bring the data together**.

### The Approach
1.  **Ingest Catalog into DuckDB**: Load the `system_catalog` (CSV/JSON) into a table in our existing DuckDB.
2.  **The "Super Power" (SQL JOIN)**:
    Now the Agent can answer complex questions with a **single query**:
    ```sql
    SELECT 
        c.department, 
        COUNT(*) as error_count
    FROM logs l
    JOIN system_catalog c ON l.service_name = c.system_name
    WHERE l.severity = 'ERROR'
    GROUP BY c.department
    ORDER BY error_count DESC
    ```

### The Workflow (Demo Flow)
For your specific demo request ("Search DB first, then Vector"):

1.  **User**: "What are the details of the critical errors in the Finance department?"
2.  **Agent (Step 1 - SQL)**:
    *   *Thought*: "I need to find which systems belong to Finance."
    *   *Action*: Query DuckDB.
    *   *SQL*: `SELECT system_name FROM system_catalog WHERE department = 'Finance'`
    *   *Result*: `['payment-service', 'billing-service']`
3.  **Agent (Step 2 - Vector)**:
    *   *Thought*: "Now I need error details for these specific services."
    *   *Action*: Query Knowledge Base.
    *   *Filter*: `service_name IN ['payment-service', 'billing-service']`
    *   *Result*: "Payment service failed due to timeout..."

## 4. Why this is better?
*   **Performance**: SQL Joins are instant. Agentic loops ("Query A, read result, Query B") are slow.
*   **Simplicity**: We reuse the existing `SQLGenerator` tool. We just give it a new table (`system_catalog`) to play with.
*   **Control**: LangGraph manages the flow, giving us full visibility into the "Reasoning Steps".

## 5. Implementation Plan
1.  **Create Catalog**: `data/system_catalog.csv` (System, Dept, Owner).
2.  **Load Catalog**: Update `LogIngestor` or `BulkLoader` to load this CSV into DuckDB on startup.
3.  **Update Prompts**: Tell the `SQLGenerator` about the new `system_catalog` table schema.
