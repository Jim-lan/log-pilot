# 📋 Functional Review Checklist

This document lists the core functional units of the LogPilot V2 microservices architecture. Use this checklist to review the implementation, verify concerns, and ensure all requirements are met.

## 1. 📥 Ingestion Layer (`services/ingestion-worker`, `services/bulk-loader`)

### **PII Masking** (`shared/utils/pii_masker.py`)
- [x] **Data Types**: Verify we are masking:
    - Email Addresses
    - IPv4 Addresses
    - Credit Card Numbers
    - SSNs / US Phone Numbers
- [x] **Method**: Regex-based replacement (e.g., `<EMAIL>`, `<IP>`).
- [x] **Concern**: Are we missing any custom PII patterns (e.g., API keys, internal IDs)?
- [x] **Concern**: Is masking applied *before* any storage or LLM processing?

### **Template Mining** (`Drain3` : `shared/utils/template_miner.py`)
- [x] **Function**: Extracts constant templates from variable log messages.
- [x] **Concern**: Is the `sim_th` (similarity threshold) tuned correctly? (Set to 0.5 in `shared/utils/template_miner.py`)
- [x] **Concern**: How do we handle template drift over time? (Handled by `Drain3` tree evolution & persistence)

### **Log Parsing** (`shared/utils/log_parser.py`)
- [x] **Function**: structured extraction of `timestamp`, `severity`, `service`, `message`. (Updated to use Regex)
- [x] **Concern**: Handling of multi-line logs (stack traces). (Supported via `re.DOTALL` in `LogParser`)
- [x] **Concern**: Timezone normalization (UTC). (Implemented in `LogParser`)

---

## 2. 🕵️ Schema Discovery (`services/schema_discovery`)

### **Regex Generator** (`src/generator.py`)
- [x] **Function**: LLM generates Python regex from raw log samples.
- [x] **Prompting**: Does the prompt enforce named groups (`?P<name>`)? (Yes, prompt updated)
- [x] **Concern**: Handling of varying log formats within the same service. (LLM handles this via generalization)

### **Regex Validator** (`src/validator.py`)
- [x] **Function**: Compiles and tests regex against *all* provided samples.
- [x] **Strictness**: Does it require 100% match? (Yes, `pattern.match`)
- [x] **Concern**: Preventing "too broad" regexes (e.g., `.*`) that match everything but extract nothing. (Fixed: Enforces named groups)

### **Orchestration** (`src/agent.py`)
- [x] **Function**: Retry loop (Generate -> Validate -> Retry).
- [x] **Concern**: Max retries configuration. (Default 3)

---

## 3. 🧠 Knowledge Base (`services/knowledge_base`)

### **Ingestion** (`src/store.py`, `src/converter.py`)
- [x] **Function**: Converts `LogEvent` -> LlamaIndex `Document`.
- [x] **Metadata**: Are we indexing `service_name`, `severity`, `timestamp` for filtering? (Yes, in `LogConverter`)
- [x] **Concern**: Embedding cost and latency for high-volume logs. **(ACCEPTED RISK: Prototype embeds all. Future: Embed templates only)**

### **Retrieval** (`src/store.py`)
- [x] **Function**: Semantic search using Vector Store (ChromaDB).
- [x] **Concern**: Top-k retrieval size. **(Default: 2. Future: Tune based on context window)**
- [x] **Concern**: Relevance threshold. **(Future: Add similarity score filter)**

---

## 4. 🚁 Pilot Orchestrator (`services/pilot_orchestrator`)

### **Intent Classification** (`src/nodes.py`)
- [x] **Function**: Routes query to `SQL` (Data) or `RAG` (Knowledge).
- [x] **Logic**: Keyword heuristics (Prototype) / LLM classifier (Planned).
- [x] **Concern**: Ambiguous queries. (Handled by fallback logic)

### **SQL Generation** (`src/tools/sql_tool.py`)
- [x] **Function**: Text-to-SQL for DuckDB.
- [x] **Schema Visibility**: Does the LLM know the table schema? (Yes, injected in prompt)
- [x] **Concern**: SQL Injection prevention. (Read-only connection recommended)

### **RAG & Synthesis** (`src/nodes.py`)
- [x] **Function**: Combines retrieved context/SQL results into a natural language answer.

---

## 5. 🌐 API Gateway (`services/api_gateway`)

### **Interface** (`src/main.py`)
- [x] **Function**: `POST /query` endpoint.
- [x] **Concern**: Error handling. (Basic try/except implemented)

---

## 6. 📊 Evaluator (`services/evaluator`)

### **Metrics** (`src/scorer.py`)
- [x] **Regex**: Functional correctness (matches samples).
- [x] **SQL**: String normalization match.
- [x] **RAG**: Keyword overlap.

### **Datasets** (`data/golden_datasets/`)
- [x] **Coverage**: Initial datasets created.

---

## 7. 📚 System Catalog & Advanced (`data/system_catalog.csv`)

### **Unified Data Layer**
- [x] **Function**: Maps technical services to business metadata (Department, Owner).
- [x] **Integration**: Loaded into DuckDB for SQL JOINs.
- [x] **Scenario**: Many-to-Many relationships (e.g., Auth Service -> Security & Finance).

### **Local LLM Support**
- [x] **Function**: `LLMClient` supports `provider="local"`.
- [x] **Verification**: `scripts/compare_models.py` benchmarks Local vs. Cloud.
