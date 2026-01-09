# LogPilot 🚀
**Intelligent Observability Agent**

LogPilot is an AI-powered observability assistant that allows you to query your system logs using natural language. Instead of writing complex SQL or Grep commands, simply ask "How many errors in auth-service?" and get instant answers.

## ✨ Features
- **Natural Language Querying**: Chat with your logs like a human.
- **Multi-Turn Context**: Understands follow-up questions (e.g., "List them", "Show details").
- **Hybrid Intelligence**: Combines **SQL Generation** (for precise data) and **RAG** (for runbooks/knowledge).
- **Modern UI**: Beautiful, dark-mode web interface with chat history.
- **Local Privacy**: Runs 100% locally using Docker and Ollama (Llama 3 / Phi-3).

## 🛠️ Tech Stack
- **AI/LLM**: Llama 3 (via Ollama), LangGraph (Orchestration), LlamaIndex (RAG).
- **Backend**: Python, FastAPI, DuckDB (High-performance OLAP).
- **Evaluation**: Ragas, FastAPI (Microservice).
- **Frontend**: Vanilla JS, HTML5, CSS3 (Glassmorphism).
- **Infrastructure**: Docker Compose.

## 💻 System Requirements & LLM Options
LogPilot runs the LLM locally by default, which requires system RAM.

### 1. Default (Recommended)
*   **Model**: `Llama 3` (8B Parameters).
*   **RAM Required**: ~8GB total system RAM (allocates ~4.5GB for model).
*   **Performance**: Best balance of speed and reasoning capability.

### 2. High Performance (Workstation / Server)
*   **Model**: `Llama 3` (70B) or `Mixtral` (8x7B).
*   **RAM Required**: ~48GB+ system RAM (or dual GPU setup).
*   **Performance**: GPT-4 class reasoning locally.
*   **How to Switch**:
    ```bash
    # In docker-compose.yml
    command: -c "ollama serve & sleep 5 && ollama pull llama3:70b && wait"
    ```

### 3. Cloud / High Performance (No Local RAM)
If you have low RAM or want GPT-4 class performance, point LogPilot to a cloud provider.
*   **Supported**: OpenAI, Anthropic, Groq.
*   **Configuration**:
    ```bash
    # Set env vars in docker-compose.yml
    LLM_BASE_URL=https://api.openai.com/v1
    LLM_API_KEY=sk-...
    LLM_MODEL=gpt-4o
    ```

## 🚀 How to Use
1.  **Start the System**:
    ```bash
    docker compose up --build -d
    ```
2.  **Access the UI**: Open `http://localhost:3000`.
3.  **Ask Questions**:
    - "How many errors in the last 24 hours?"
    - "Which service has the most failures?"
    - "List the errors in payment-service."
4.  **Evaluate Performance**:
    -   Trigger batch evaluation: `curl -X POST http://localhost:8002/evaluate/batch -d '{}'`

## 💡 Design Thought
LogPilot is built on the **"Router-Solver"** pattern with **Agentic RAG**. A central orchestrator classifies user intent and routes the query to specialized tools:
- **SQL Tool**: Converts questions into DuckDB SQL for hard data analysis.
- **RAG Tool**: Retrieves context from runbooks for troubleshooting advice.
- **Self-Correction**: The agent verifies its own answers (Context Relevance & Hallucination Check) before responding.
- **Query Rewriter**: Ensures multi-turn conversations are robust by rewriting follow-ups into standalone queries.

This architecture ensures high precision (SQL) and helpful context (RAG) while maintaining a natural user experience.

## 📚 Documentation Center

### 🟢 For Everyone
-   [**Detailed Architecture**](docs/architecture.md): The blueprint of the system (Flowcharts, Components).
-   [**Project Roadmap & Backlog**](docs/backlog.md): Future plans, risks, and enhancement ideas.
-   [**Design History**](docs/design_history/agent_design.md): Evolution of the agentic design.

### 🔵 For Developers
-   [**Technical Reference**](docs/technical_reference.md): Code structure, modules, and setup.
-   [**API Reference**](docs/api_reference.md): Endpoints and payloads.
-   [**Security Guide**](docs/security_deployment.md): Deployment hardening and PII masking.

### 🟣 For Performance
-   [**Performance Benchmarks**](docs/performance_benchmarks.md): Latency and accuracy metrics.
-   [**Review Findings**](docs/design_review_findings.md): Past architectural reviews.
