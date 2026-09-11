# API Reference 📡

## Base URL
`http://localhost:8000`

## Endpoints

### 1. Run Query
Executes the Pilot Agent for a given natural language query.

-   **URL**: `/query`
-   **Method**: `POST`
-   **Content-Type**: `application/json`

#### Request Body
```json
{
  "query": "Show me the last 5 errors in auth-service"
}
```

| Field | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `query` | string | The natural language question to ask the agent. | Yes |

#### Response (200 OK)
```json
{
  "answer": "Here are the last 5 errors...",
  "sql": "SELECT * FROM logs ...",
  "sql_result": "[('ERROR', ...)]",
  "context": "Runbook: How to fix auth errors...",
  "intent": "sql"
}
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `answer` | string | The final natural language response. |
| `sql` | string | The generated SQL query (if intent was SQL). |
| `sql_result` | string | The raw result from the database (stringified). |
| `context` | string | Retrieved context from RAG (if intent was RAG). |
| `intent` | string | Classified intent (`sql`, `rag`, `ambiguous`). |
| `metadata` | object | Rewritten query, elapsed latency, and validation feedback when available. |
| `trace` | array | Serialized messages supplied by the graph; supports stored history dictionaries and message objects, preserving tool calls when present. |

Conversation compatibility: follow-up requests can serialize existing dictionary-based history without an HTTP 500. The last ten prior messages are sent to the graph. The API still uses the shared `default` session; user isolation remains planned. The current trace is a message transcript, not a complete execution-event audit trail.

Graph validation now uses independent retry counters (three SQL repairs; two context and two answer retries). `metadata.retry_counts` reports `sql`, `context` and `answer`. `metadata.outcome` may be `validated`, `insufficient_evidence` or `dependency_error`; `validated` means the configured judge accepted the answer, not that factual correctness is guaranteed. These are additive fields. Transport/request exceptions still use HTTP error responses.

When the answer judge repeatedly rejects or cannot parse its response, the returned answer explicitly abstains. An enabled RAG-to-web fallback returns `intent: "web_search"` and the web evidence in `context`, rather than the rejected RAG context. External search is disabled unless the operator sets `LOGPILOT_ALLOW_WEB_SEARCH=true`; this flag permits sending the rewritten question to the external search provider. Search absence/outage does not become supporting evidence for synthesis. Authentication, comprehensive egress redaction and overall request deadlines are still pending.

---

### 2. Get Chat History
Retrieves the chat history for the default session.

-   **URL**: `/history`
-   **Method**: `GET`

#### Response (200 OK)
```json
[
  {
    "role": "user",
    "content": "Hello",
    "timestamp": "2023-10-27 10:00:00"
  },
  {
    "role": "ai",
    "content": "Hi there! How can I help?",
    "timestamp": "2023-10-27 10:00:05"
  }
]
```

---

### 3. Health Check
Checks the status of the API and the LLM connection.

-   **URL**: `/health`
-   **Method**: `GET`

#### Response (200 OK)
```json
{
  "status": "ok",
  "llm": {
    "status": "connected",
    "model": "gemma4:e4b"
  }
}
```

## MCP database operations

`query_logs`, `logs://recent` and `logs://schema` use the connector's transient `query()` method with a read-only logs connection. They preserve their string result/error contracts. `ask_log_pilot` forwards to the API with a 60-second HTTP timeout. This compatibility repair does not add authorization, SQL sandboxing or new transport guarantees.
