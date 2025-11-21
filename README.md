# GenAI LogPilot 🚁

> **An intelligent log management system powered by LLMs for natural language querying, anomaly detection, and automated root cause analysis.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

---

## 🎯 What is LogPilot?

LogPilot is an **enterprise-grade log management platform** that goes beyond traditional grep/Splunk by using **Large Language Models (LLMs)** to understand log semantics, group errors intelligently, and provide actionable insights through natural language queries.

### Key Differentiators
- **Natural Language Querying**: Ask "Why did User 123 fail?" instead of writing complex regex
- **Template Mining**: Automatically extracts patterns from millions of logs (Drain3-based)
- **PII Masking**: Built-in privacy protection for sensitive data (emails, SSNs, credit cards)
- **Hybrid Storage**: DuckDB for structured queries + ChromaDB for semantic search
- **Enterprise-Ready**: RBAC, encryption, audit trails, tiered storage

---

## 🏗️ Architecture Overview
 
LogPilot follows a **Data Lakehouse + RAG** architecture with a **Hybrid Agentic Control Plane**:
 
```mermaid
graph TB
    subgraph "Phase 1 & 2: Data Plane"
        Raw[Raw Logs] -->|Ingest| Worker[Ingestion Worker]
        Worker -->|PII Masking| Clean[Cleaned Logs]
        Clean -->|Template Mining| Registry[(Schema Registry)]
        Clean -->|Batch Insert| DuckDB[(DuckDB)]
    end
    
    subgraph "Phase 3 & 4: Control Plane (Agent)"
        User[User API] -->|REST| Gateway[API Gateway]
        Gateway -->|Chat| Pilot[Pilot Orchestrator (LangGraph)]
        
        Pilot -->|SQL| SQLTool[SQL Generator]
        SQLTool --> DuckDB
        
        Pilot -->|RAG| KB[Knowledge Base (LlamaIndex)]
        KB -->|Vector Search| Chroma[(ChromaDB)]
        
        Pilot -->|Answer| Gateway
    end
```
 
### Key Components
 
| Component | Tech Stack | Function | Status |
|-----------|------------|----------|--------|
| **Ingestion Worker** | Python, Kafka | Real-time log streaming & PII masking | ✅ Complete |
| **Schema Registry** | Python, Regex | Template mining### 3. **Intelligence Layer (The "Brain")**
*   **Pilot Orchestrator (LangGraph)**: A cyclic state machine that routes queries to the right tool (SQL vs. RAG), handles self-correction, and synthesizes answers.
*   **Knowledge Base (LlamaIndex)**: RAG engine for semantic search over unstructured logs and documentation.
*   **Schema Discovery Agent**: LLM-powered agent that automatically generates and validates regex patterns for new log types.

### 4. **Interface & Evaluation**
*   **API Gateway (FastAPI)**: RESTful interface for external clients.
*   **Evaluator Service**: Framework for benchmarking agent performance against golden datasets.
eway** | **FastAPI** | Headless REST interface | 🚧 In Progress |
 
---
 
## 📁 Project Structure (V2)
 
```
log-pilot/
├── config/                 # Centralized Config (LLM, Agents)
├── prompts/                # Jinja2 Prompt Templates
├── services/
│   ├── api-gateway/        # FastAPI Interface
│   ├── ingestion-worker/   # Data Plane
│   ├── pilot-orchestrator/ # LangGraph Agent
│   ├── knowledge-base/     # LlamaIndex RAG
│   └── schema-registry/    # Template Cache
├── shared/
│   ├── llm/                # Unified LLM Client
│   ├── db/                 # DuckDB Connector
│   └── utils/              # PII Masker
└── tests/                  # Integration & E2E Tests
```
 
---
 
## 🚀 Quick Start
 
### Prerequisites
- **Python**: 3.9+
- **API Keys**: OpenAI or Gemini (set in `.env`)
 
### 1. Setup Environment
```bash
./scripts/init_dev_env.sh
```
 
### 2. Run Tests
```bash
pytest tests/
```
 
---
 
## 📚 Documentation
*   **[Business Overview](docs/business_overview.md)**: High-level explanation of the architecture and value (Start Here!).
*   **[Architecture](docs/architecture.md)**: Detailed technical specifications.
*   **[Workflow](docs/workflow.md)**: Data flow diagrams.
- **[Agent Framework](docs/agent_design.md)**: LangGraph & LlamaIndex design details
- **[System Components](docs/system_components.md)**: Service breakdown
- **[Testing Strategy](docs/testing_strategy.md)**: Unit, Integration, E2E standards
 
---
 
## 🛣️ Roadmap
 
### ✅ Phase 1 & 2: Data Foundation
- Historical & Streaming Ingestion
- PII Masking & Template Mining
- DuckDB Persistence
 
### 🚧 Phase 3 & 4: Agentic Intelligence (Current)
- **LangGraph Orchestrator**: Self-correcting agent flow
- **LlamaIndex RAG**: Advanced retrieval
- **API Gateway**: Headless interface
 
### 🔮 Phase 5: Enterprise Features
- RBAC & Audit Trails
- Predictive Analytics

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) first.

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Drain3**: For log template mining algorithm
- **DuckDB**: For high-performance analytical queries
- **ChromaDB**: For vector storage (planned integration)
- **LangChain**: For LLM orchestration (planned integration)

---

## 📞 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/log-pilot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/log-pilot/discussions)
- **Email**: support@logpilot.dev

---

**Built with ❤️ for DevOps, SRE, and Security teams who deserve better log analytics.**
