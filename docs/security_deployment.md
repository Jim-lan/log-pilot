# Security & Deployment Guide 🛡️

## Security

### 1. PII Masking
The Ingestion Worker automatically masks sensitive data before it enters the database.
-   **Emails**: Replaced with `[EMAIL]`
-   **IP Addresses**: Replaced with `[IP]`
-   **SSN/Credit Cards**: Replaced with `[REDACTED]`
-   **Implementation**: Regex-based masking in `services/ingestion-worker/src/pii_masker.py`.

### 2. Database Access Control
-   **Ingestion Worker**: Has **Read-Write** access to `logs.duckdb`.
-   **Pilot Orchestrator**: Has **Read-Only** access to `logs.duckdb`. This prevents the LLM from accidentally modifying or deleting log data (SQL Injection protection).

### 3. Network Isolation
-   Services run in a dedicated Docker network (`log-pilot-net`).
-   Only the **Frontend** (port 3000) and **Pilot API** (port 8000) are exposed to the host.
-   The Database files are mounted as volumes but are not exposed via network ports.

---

## Deployment

### Prerequisites
-   **Docker** & **Docker Compose**
-   **Python 3.9+** (for local development)
-   **Ollama** (running locally or accessible via network)

### Environment Variables
Create a `.env` file in the root directory:

```bash
# LLM Configuration
LLM_BASE_URL=http://host.docker.internal:11434
LLM_MODEL=llama3

# Database Paths
LOGS_DB_PATH=data/target/logs.duckdb
HISTORY_DB_PATH=data/target/history.duckdb
CHROMA_DB_PATH=data/target/chroma_db
```

### Production Mode
To run in production mode (detached):

```bash
docker compose up -d --build
```

### Development Mode
To run with hot-reloading (mapped volumes):

```bash
# Ensure docker-compose.yml has volumes mapped for source code
docker compose up --build
```

### Troubleshooting
-   **"Connection Refused"**: Ensure Ollama is running and accessible.
-   **"Database Locked"**: Ensure only one writer (Ingestion Worker) is active.
