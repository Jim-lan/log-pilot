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
    "model": "llama3"
  }
}
```
