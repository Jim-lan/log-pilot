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
- **Frontend**: Vanilla JS, HTML5, CSS3 (Glassmorphism).
- **Infrastructure**: Docker Compose.

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
4.  **Connect External Agents (MCP)**:
    -   LogPilot exposes an MCP Server at `http://localhost:8001/sse`.
    -   **Claude Desktop**: Add this to your config:
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

## 💡 Design Thought
LogPilot is built on the **"Router-Solver"** pattern. A central orchestrator classifies user intent (Data vs. Knowledge) and routes the query to specialized tools:
- **SQL Tool**: Converts questions into DuckDB SQL for hard data analysis.
- **RAG Tool**: Retrieves context from runbooks for troubleshooting advice.
- **Query Rewriter**: Ensures multi-turn conversations are robust by rewriting follow-ups into standalone queries.

This architecture ensures high precision (SQL) and helpful context (RAG) while maintaining a natural user experience.

## 📚 Documentation
-   [Detailed Architecture](docs/architecture_detailed.md)
-   [API Reference](docs/api_reference.md)
-   [Security & Deployment](docs/security_deployment.md)
-   [Performance Benchmarks](docs/performance_benchmarks.md)
-   [Original Architecture](architecture.md)
