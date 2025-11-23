# 📜 LogPilot Script Catalog

This document serves as a comprehensive catalog of all executable scripts and modules within the LogPilot project.

## 📂 Services

### 🧠 Pilot Orchestrator (`services/pilot-orchestrator/`)
| Script | Function | Goal |
|--------|----------|------|
| `src/agent.py` | `LogPilotAgent` class | **(Legacy)** Phase 3 mock agent. Routes queries to SQL or RAG tools based on keyword intent. |
| `src/tools/sql_tool.py` | `SQLGenerator` class | Converts natural language queries into DuckDB SQL using regex heuristics. |
| `tests/test_agent.py` | Unit Test | Verifies the routing logic of the `LogPilotAgent`. |

### 📚 Knowledge Base (`services/knowledge_base/`)
| Script | Function | Goal |
|--------|----------|------|
| `src/main.py` | CLI Entry Point | Allows interactive testing of the Knowledge Base (ingest & query). |
| `src/store.py` | `KnowledgeStore` class | Manages the LlamaIndex Vector Store (ChromaDB) for document ingestion and retrieval. |
| `src/converter.py` | `LogConverter` class | Converts `LogEvent` objects into LlamaIndex `Document` objects with metadata. |
| `tests/test_store.py` | Unit Test | Verifies `KnowledgeStore` logic (add_logs, query) using mocks. |

### 🌐 API Gateway (`services/api_gateway/`)
| Script | Function | Goal |
|--------|----------|------|
| `src/main.py` | `app` (FastAPI) | **REST Interface**: Exposes `POST /query` to interact with the Pilot Orchestrator. |
| `src/models.py` | Pydantic Models | Defines request/response schemas (`QueryRequest`, `QueryResponse`). |
| `tests/test_api.py` | Unit Test | Verifies API endpoints and integration with the Orchestrator (mocked). |

### 🕵️ Schema Discovery (`services/schema_discovery/`)
| Script | Function | Goal |
|--------|----------|------|
| `src/agent.py` | `DiscoveryAgent` class | **Orchestrator**: Manages the Generate -> Validate loop to find working regexes. |
| `src/generator.py` | `RegexGenerator` class | **LLM**: Asks the LLM to generate a regex pattern for log samples. |
| `src/validator.py` | `RegexValidator` class | **Validation**: Compiles and tests the regex against samples to ensure correctness. |
| `tests/test_agent.py` | Unit Test | Verifies the retry logic and validation flow (mocked). |

### 📊 Evaluator Service (`services/evaluator/`)
| Script | Function | Goal |
|--------|----------|------|
| `src/runner.py` | `EvalRunner` class | **Execution**: Runs agents against Golden Datasets. |
| `src/scorer.py` | `EvalScorer` class | **Metrics**: Calculates accuracy scores for Regex, SQL, and RAG. |
| `scripts/benchmark_agents.py` | CLI Script | **Benchmarking**: Runs the evaluation suite and prints results. |
| `scripts/e2e_test.sh` | Shell Script | **E2E Testing**: Automates cleanup, ingestion, and evaluation. |

### 📥 Ingestion Worker (`services/ingestion-worker/`)
| Script | Function | Goal |
|--------|----------|------|
| `src/main.py` | `LogIngestor` class | **Real-Time Ingestion**: Consumes logs (Mock Kafka), masks PII, mines templates, and batch inserts into DuckDB. |

### 🚚 Bulk Loader (`services/bulk-loader/`)
| Script | Function | Goal |
|--------|----------|------|
| `src/log_loader.py` | `BulkLoaderJob` class | **Historical Ingestion**: Scans files, masks PII, mines templates, and loads data into DuckDB. |

## 📦 Shared Libraries (`shared/`)

| Script | Function | Goal |
|--------|----------|------|
| `llm/client.py` | `LLMClient` class | **Unified LLM Interface**: Abstracts OpenAI/Gemini API calls (currently mock). |
| `llm/prompt_factory.py` | `PromptFactory` class | **Prompt Management**: Loads and renders Jinja2 prompt templates. |
| `db/duckdb_client.py` | `DuckDBConnector` class | **Database Access**: Handles DuckDB connections and batch insertions. |
| `utils/pii_masker.py` | `PIIMasker` class | **Security**: Redacts sensitive info (Email, IP, SSN) using Regex. |
| `utils/log_parser.py` | `LogParser` class | **Parsing**: Robust Regex-based parsing with UTC normalization. |
| `log_schema.py` | `LogEvent` class | **Data Model**: Defines the Golden Standard Schema (Pydantic model). |

## 🛠️ Configuration

| File | Goal |
|------|------|
| `config/llm_config.yaml` | Central configuration for LLM providers (OpenAI, Gemini) and agent parameters. |
