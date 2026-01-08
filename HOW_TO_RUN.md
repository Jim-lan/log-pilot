# 🚀 How to Run LogPilot V2

This guide provides step-by-step instructions to set up, run, and test the LogPilot V2 system.

## 📋 Prerequisites
- **Docker & Docker Compose** (Essential)
- **Python 3.9+** (For local testing/scripts)
- **Hardware**:
    - Minimum: 8GB RAM (Llama 3 8B)
    - Recommended: 16GB+ RAM or NVIDIA GPU

## 🛠️ Quick Start (Docker)

The easiest way to run LogPilot is via Docker Compose. This spins up all 6 services:
1.  **LLM Service** (Ollama)
2.  **Ingestion Worker** (Mock Data)
3.  **Pilot Orchestrator** (The Brain)
4.  **Frontend** (UI)
5.  **MCP Server** (External Tooling)
6.  **Evaluation Service** (Metrics)

### 1. Start the System
```bash
docker compose up --build -d
```
*   **Wait**: Give it ~30s for the LLM to pull the model (`llama3`).
*   **Check**: `docker ps` should show all containers running.

### 2. Access the UI
Open **http://localhost:3000** in your browser.
*   **Try**: "How many errors in the last hour?"
*   **Try**: "How do I fix the 503 error?"

### 3. Access the API
*   **Pilot API**: `http://localhost:8000/docs`
*   **Eval API**: `http://localhost:8002/docs`

### 4. Stop the System
```bash
docker compose down
```

## 🧪 Advanced Usage

### A. Run Evaluation (Batch)
To test the agent's accuracy against the Golden Dataset:
```bash
curl -X POST http://localhost:8002/evaluate/batch \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}'
```
Results are stored in `data/target/metrics.duckdb`.

### B. Connect via MCP (Claude Desktop)
LogPilot exposes an MCP Server at `http://localhost:8001/sse`.
Add this to your Claude Desktop config:
```json
{
  "mcpServers": {
    "log-pilot": {
      "url": "http://localhost:8001/sse",
      "transport": "sse"
    }
  }
}
```

### C. Run Local Tests (Developers)
If you are developing locally:
```bash
# 1. Create Venv
python3 -m venv venv
source venv/bin/activate

# 2. Install Deps
pip install -r requirements.txt

# 3. Run Tests
pytest
```

## 📂 Key Files
- **`docker-compose.yml`**: Service definitions.
- **`config/`**: Configuration files.
- **`data/`**: Data storage (DuckDB, ChromaDB).
- **`docs/`**: Detailed documentation.
