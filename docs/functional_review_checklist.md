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
- [ ] **Concern**: Embedding cost and latency for high-volume logs. **(VALID: Currently embeds every log. Should optimize to embed templates only)**

### **Retrieval** (`src/store.py`)
- [x] **Function**: Semantic search using Vector Store (ChromaDB).
- [ ] **Concern**: Top-k retrieval size (is 5 or 10 enough context?). **(MISSING: Uses default top_k=2)**
- [ ] **Concern**: Relevance threshold (filtering out noise). **(MISSING: No threshold set)**

---

## 4. 🚁 Pilot Orchestrator (`services/pilot_orchestrator`)

### **Intent Classification** (`src/nodes.py`)
- [ ] **Function**: Routes query to `SQL` (Data) or `RAG` (Knowledge).
- [ ] **Logic**: Keyword heuristics vs. LLM classifier.
- [ ] **Concern**: Ambiguous queries (e.g., "What happened yesterday?" could be both).

### **SQL Generation** (`src/tools/sql_tool.py`)
- [ ] **Function**: Text-to-SQL for DuckDB.
- [ ] **Schema Visibility**: Does the LLM know the table schema (`logs` table)?
- [ ] **Concern**: SQL Injection prevention (though read-only).
- [ ] **Concern**: Hallucinating non-existent columns.

### **RAG & Synthesis** (`src/nodes.py`)
- [ ] **Function**: Combines retrieved context/SQL results into a natural language answer.
- [ ] **Concern**: Hallucination (making up facts not in context).
- [ ] **Concern**: Answer tone and helpfulness.

---

## 5. 🌐 API Gateway (`services/api_gateway`)

### **Interface** (`src/main.py`)
- [ ] **Function**: `POST /query` endpoint.
- [ ] **Concern**: Error handling (returning 500 vs 400).
- [ ] **Concern**: Latency (synchronous LangGraph invocation).

---

## 6. 📊 Evaluator (`services/evaluator`)

### **Metrics** (`src/scorer.py`)
- [ ] **Regex**: Functional correctness (matches samples).
- [ ] **SQL**: String normalization match (vs execution match).
- [ ] **RAG**: Keyword overlap (Jaccard).
- [ ] **Concern**: Are these metrics robust enough?

### **Datasets** (`data/golden_datasets/`)
- [ ] **Coverage**: Do we have enough diverse examples?
- [ ] **Concern**: Maintenance of golden data as schema changes.
