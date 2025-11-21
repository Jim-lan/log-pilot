# LogPilot Folder Structure V2 (Proposed)

To support the new **Hybrid Architecture** (LangGraph + LlamaIndex), we recommend restructuring the project to separate concerns clearly.

## Proposed Structure

```text
log-pilot/
├── config/                 # Central Configuration
│   ├── llm_config.yaml     # Model providers & params
│   └── agents.yaml         # Agent-specific settings
│
├── data/                   # Data Storage
│   ├── logs.duckdb         # Structured Logs
│   ├── vector_store/       # ChromaDB (LlamaIndex)
│   └── landing_zone/       # Raw Files
│
├── docs/                   # Documentation
│   ├── architecture.md
│   ├── agent_design.md
│   └── ...
│
├── prompts/                # Jinja2 Prompt Templates
│   ├── schema_discovery/
│   └── pilot_orchestrator/
│       ├── classifier.j2
│       └── sql_gen.j2
│
├── services/
│   ├── api-gateway/        # NEW: FastAPI Interface
│   │   ├── src/
│   │   │   ├── main.py     # App entry point
│   │   │   └── routers/    # API routes
│   │   └── tests/
│   │
│   ├── ingestion-worker/   # Phase 2: Data Plane (Kafka -> DuckDB)
│   │   ├── src/
│   │   └── tests/          # Unit Tests
│   │
│   ├── schema-registry/    # Phase 4: Schema Discovery Agent
│   │   ├── src/
│   │   └── tests/          # Unit Tests
│   │
│   ├── pilot-orchestrator/ # Phase 3/4: Control Plane (LangGraph)
│   │   ├── src/
│   │   │   ├── graph.py    # StateGraph definition
│   │   │   ├── nodes/      # Graph nodes (classify, sql, etc.)
│   │   │   └── state.py    # AgentState definition
│   │   ├── tests/          # Unit Tests
│   │   └── main.py
│   │
│   └── knowledge-base/     # NEW: RAG Service (LlamaIndex)
│       ├── src/
│       │   ├── index.py    # Index management
│       │   └── query.py    # Retrieval logic
│       ├── tests/          # Unit Tests
│       └── documents/      # Source docs for RAG
│
├── tests/                  # Integration & E2E Tests
│   ├── integration/
│   └── e2e/
│
├── shared/                 # Shared Libraries
│   ├── llm/                # LLM Client & PromptFactory
│   ├── db/                 # DuckDB Connector
│   └── models/             # Pydantic Schemas
│
└── scripts/                # Setup & Utility Scripts
```

## Key Changes
1.  **`services/knowledge-base/`**: New service dedicated to LlamaIndex RAG operations (replacing part of `tool-service`).
2.  **`services/pilot-orchestrator/`**: Restructured for LangGraph (nodes, graph, state).
3.  **`prompts/`**: Top-level directory for prompt templates.
4.  **`config/`**: Top-level directory for centralized config.
