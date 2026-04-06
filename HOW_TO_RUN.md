# 🚀 LogPilot: System & Demo Guide

Welcome to **LogPilot**! This guide will help you understand, run, and demonstrate the capabilities of this autonomous log analysis agent.

**What is LogPilot?**
LogPilot is an AI Agent that doesn't just "chat"—it uses tools. It combines the precision of SQL (for data) with the reasoning of LLMs (for knowledge) to solve infrastructure problems, just like a human SRE.
- 🧠 **Brain**: A LangGraph agent that plans, routes, and corrects itself.
- 📚 **Memory**: A Vector Database (Chroma) for reading runbooks.
- 👁️ **Vision**: A Sentry Service that watches for anomalies 24/7.

---

## ✅ Prerequisites

Before you start, ensure you have:
1.  **Docker Desktop** installed and running.
2.  **8GB+ RAM** available (for running the local LLM).
3.  **Ports Available**: 8000 (API), 8001 (MCP), 3000 (Frontend).

---

## 🎬 Quick Start: Running the Demo

We will run the entire stack (Brain, UI, Ingestion, Database) in Docker containers.

### Step 1: Clean Slate
First, let's make sure no old processes are blocking our ports.
```bash
# MacOS / Linux
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
# Or just ensuring Docker is clean
docker-compose down
```

### Step 2: Launch the Stack
This command builds the services and starts them in the background.
```bash
docker-compose up --build -d
```
> ⏳ **Wait Sequence**:
> 1.  **Build**: ~1-2 minutes on first run.
> 2.  **Startup**: Wait for the "Brain" to wake up. You can check with: `docker logs -f log-pilot-brain`.
> 3.  **Ready**: When you see `Uvicorn running on http://0.0.0.0:8000`.

### Step 2.5: Verify Status (Optional)
Run this command to confirm your agents are alive:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```
You should see all 6 services running:
*   `log-pilot-brain` (Orchestrator)
*   `log-pilot-ui` (Frontend)
*   `log-pilot-sentry` (Watchdog)
*   `log-pilot-ingestion` (Worker)
*   `log-pilot-llm` (Ollama)
*   `log-pilot-generator` (Admin Console)

### Step 3: Open the Cockpit
Navigate to **[http://localhost:3000](http://localhost:3000)** in your browser.

---

## 🧪 Demo Scenarios

Follow this script to demonstrate the agent's evolving intelligence.

### Scenario 1: The "New Hire" Phase (Baseline)
**Goal**: Show that without knowledge, the AI is smart but limited.

1.  **Action**: Go to the Chat UI and ask:
    > *"How do I restart the payment service?"*
2.  **What to Expect**:
    *   The AI will think for a moment.
    *   It will likely say: *"I don't have enough information to answer that"* or try to search the web generically.
3.  **Why?** (Behind the Scenes):
    *   The **Router** checked its internal knowledge (RAG) and found nothing about "payment service" in the database.
    *   It **fell back to Web Search** (the designed safety net), or simply admitted ignorance if internet access is disabled.
    *   This proves that without the Runbook, the Local knowledge base is empty.

### Scenario 2: Knowledge Injection (Teaching)
**Goal**: Teach the AI by giving it a Runbook.

1.  **Action**: Run this command in your terminal:
    ```bash
    docker exec -it log-pilot-generator python scripts/demo_inject_knowledge.py --runbook payment_runbook.md
    ```
2.  **What to Expect**:
    *   Terminal output: `✅ Runbook copied...` and `✅ Ingestion Worker processed...`.
3.  **Why?** (Behind the Scenes):
    *   You dropped a Markdown file into the `landing_zone`.
    *   The **Ingestion Worker** detected the file event.
    *   It read the text, split it into chunks, embedded them into vectors, and stored them in **ChromaDB**. Now the AI has "memory".

### Scenario 3: The "Expert SRE" Phase (RAG)
**Goal**: Verify the AI can now solve the problem.

1.  **Action**: Ask the exact same question again in the UI:
    > *"How do I restart the payment service?"*
2.  **What to Expect**:
    *   The AI answers confidently: *"To restart the payment service, first drain the node, then execute `systemctl restart payment`..."*
3.  **Why?** (Behind the Scenes):
    *   The **Router** saw the intent "How do I..." and chose the **RAG Tool**.
    *   It queried ChromaDB for "restart payment service".
    *   It retrieved the runbook we just uploaded and used it as context to generate the answer.

### Scenario 4: The Anomaly (Sentry Spike)
**Goal**: Demonstrate the system's ability to detect issues proactively.

1.  **Action**: Simulate a disaster by generating 50 errors instantly:
    ```bash
    docker exec -it log-pilot-generator python scripts/demo_simulate_spike.py --service auth-service --count 50
    ```
2.  **What to Expect**:
    *   Within 10 seconds, a **red badge** appears on the "Alerts" tab in the UI.
    *   Clicking it shows: **"Critical: Error spike detected in auth-service"**.
3.  **Why?** (Behind the Scenes):
    *   The script injected 50 "Error" logs directly into `logs.duckdb`.
    *   The **Sentry Service** (which scans every 10s) calculated that 50 errors/min is > 1.5x the baseline.
    *   It created a structured Alert record, which the Frontend displayed instantly.

---

## 🔧 Troubleshooting

*   **Brain won't start?**
    *   Check `docker logs log-pilot-llm`. The local LLM engine (Ollama Engine) might be downloading the model (4GB). This takes time on the first run.
*   **"Connection Reset" or API crash?**
    *   Ensure you ran the cleanup command in Step 1. Port conflicts are the #1 cause of issues.
*   **Logs not appearing?**
    *   Check `docker logs log-pilot-ingestion`. Ensure it says "Persisting batch".

---

## 💡 System Internals (For the curious)

| Component | Technology | Responsibility |
| :--- | :--- | :--- |
| **Ingestion** | Python, Watchdog, Regex | Cleans, masks, and files raw logs into databases. |
| **Brain** | LangGraph, Ollama (Gemma 4) | The decision maker. Decides *how* to answer. |
| **Memory** | DuckDB (Data), Chroma (Text) | Stores the "What" (logs) and "How" (docs). |
| **Sentry** | Python, Statistical Window | The 24/7 guardian that triggers alerts. |
