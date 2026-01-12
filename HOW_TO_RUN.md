# How to Run LogPilot 🚀

Welcome to **LogPilot**, the Agentic RAG system for log analysis. This guide explains how to run the system locally for demonstration purposes.

## 📋 Prerequisites
-   **Python 3.10+** installed.
-   **DuckDB** (Python package).
-   **Ollama** running locally with `mistral` model pulled (`ollama pull mistral`).

## 🏗️ Architecture Overview
The demo consists of 3 main services:
1.  **Ingestion Worker**: watches `data/source/landing_zone` and ingests logs/docs into DuckDB & ChromaDB.
2.  **Sentry Service**: Background monitoring that detects log anomalies and triggers alerts.
3.  **Pilot Orchestrator**: FastAPI backend that powers the Chat and Agentic Logic.

## 🎬 Rapid Demo Guide

We provide a **unified startup script** to make demonstrating the platform easy.

### 1. Preparation
Ensure you have the demo runbooks in the source folder (these are typically user-supplied):
-   `data/source/http_runbook.md`
-   `data/source/new_scenario_runbook.md`

### 2. Start the Demo
Run the following command from the project root:

```bash
python3 scripts/demo_start.py
```

**What this script does:**
1.  **Cleans Environment**: Deletes old databases (`logs.duckdb`, `history.duckdb`) and previous state.
2.  **Generates Mock Data**: Creates 1,000 fresh log lines in `data/source/landing_zone`.
3.  **Launches Services**: Starts Ingestion, Sentry, and API services in the background.

### 3. Access the UI
Open `services/frontend/src/index.html` in your browser.

---

## 🎭 Demo Scenarios

Once the system is running, you can walk through these 3 scenarios to showcase value.

### Scenario A: The "Knowledge Gap" (Baseline)
**Goal:** Show that without knowledge, the AI is generic.
1.  **Ask**: "How do I fix error 404?"
2.  **Expected Result**: The AI gives a generic, Wikipedia-style answer about HTTP 404.

### Scenario B: Knowledge Injection (Agentic RAG)
**Goal:** Show how the system learns from static documents.
1.  **Run**: Inject the knowledge base.
    ```bash
    python3 scripts/demo_inject_knowledge.py --runbook http_runbook.md
    ```
2.  **Wait**: Watch the Ingestion Worker terminal (it will process the file).
3.  **Ask**: "How do I fix error 404?"
4.  **Expected Result**: The AI now gives a **specific** answer citing the "Repo-123" runbook logic.

### Scenario C: Proactive Sentry (Alerting)
**Goal:** Show the system finding issues *before* the user asks.
1.  **Action**: Simulate a massive error spike.
    ```bash
    python3 scripts/demo_simulate_spike.py --count 50
    ```
2.  **Wait**: ~10 seconds.
3.  **Observe**: 
    -   A **Red Badge** appears on the "Alerts" tab in the UI.
    -   Click the tab to see the "Error Spike Detected" alert with AI analysis.

---

## 🛠️ Advanced / Utility Scripts

The `scripts/` folder contains tools for manual control:

| Script | Purpose |
| :--- | :--- |
| `demo_start.py` | **Start Here**. Cleans DBs, gens logs, starts everything. |
| `demo_inject_knowledge.py` | Injects a specific markdown file into the system. |
| `demo_simulate_spike.py` | Injects a burst of 50 errors to trigger Sentry. |
| `generate_logs.py` | Generates generic mock logs for testing. |

---

## 📂 Project Structure

-   `services/`: Source code for the 3 main services.
-   `shared/`: Common code (DB Clients, LLM Clients) used by all services.
-   `data/`:
    -   `source/`: Where raw logs and runbooks live.
    -   `target/`: Where DuckDB and ChromaDB database files are created.
-   `tests/`: Unit and Integration tests.
-   `docs/`: Architecture diagrams and design decisions.

## ❓ Troubleshooting

**Q: The AI says "I don't know".**
A: Ensure the Ingestion Worker is running and check `data/ingestion.log` for errors.

**Q: Sentry isn't alerting.**
A: Sentry checks every 10 seconds. Ensure you injected enough errors (`--count 50`) to trip the 15% threshold.
