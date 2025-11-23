# 🔍 Overall Design Review Findings

## 1. Folder Structure & Naming Conventions
**Observation**: Service naming is inconsistent.
*   **Hyphenated**: `ingestion-worker`, `bulk-loader`, `tool-service`, `schema-registry`.
*   **Underscored**: `pilot_orchestrator`, `knowledge_base`, `api_gateway`, `schema_discovery`.

**Recommendation**: Keep **snake_case (underscores)** for Python service directories to allow module imports.
*   `pilot_orchestrator` (Kept as is)
*   `knowledge_base` (Kept as is)
*   `api_gateway` (Kept as is)
*   `schema_discovery` (Kept as is)

*Note: `ingestion-worker` and `bulk-loader` use hyphens as they are standalone scripts.*

## 2. Redundant / Legacy Services
**Observation**: Some directories appear to be leftovers from the V1 architecture.
*   **`services/tool-service/`**: The tools (`sql_tool`, `rag_retriever`) have been moved to `pilot_orchestrator` or `knowledge_base`. This directory seems to contain orphan code (`rag_retriever.py`, `test_sql_gen.py`).
*   **`services/schema-registry/`**: We are currently using `DuckDB` and `Drain3` state files as our registry. The `schema-registry` service directory (`src/api.py`) appears unused.

**Recommendation**: Archive or delete `tool-service` and `schema-registry` to reduce noise.

## 3. Code Organization
**Observation**: Test files are sometimes inside `src/`.
*   `services/pilot_orchestrator/src/test_agent.py` should be in `services/pilot_orchestrator/tests/`.

**Observation**: `pilot_orchestrator` has both `agent.py` (Legacy) and `graph.py` (New).
*   **Recommendation**: Rename `agent.py` to `agent_legacy.py` or remove it if fully replaced by `graph.py`.

## 4. Documentation
**Observation**: We have successfully consolidated the documentation into 3 main files + a history folder.
*   `docs/architecture.md` (Technical)
*   `docs/system_components.md` (Inventory)
*   `docs/business_overview.md` (Business)
*   `docs/design_history/` (Archive)

This structure is clean and maintainable.

## 5. Next Steps
1.  **Rename Directories**: Apply kebab-case standardization.
2.  **Cleanup**: Remove `tool-service` and `schema-registry`.
3.  **Move Tests**: Move `test_agent.py` to `tests/`.
