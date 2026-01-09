# LogPilot Project Backlog 📝

This document tracks identified architectural risks, performance trade-offs, and future enhancement opportunities. It serves as a repository for ideas investigated during the "Robustness 2.0" phase.

## 1. Architectural Risks & Mitigations 🛡️

### A. Latency Impact (Router Overhead)
*   **Risk**: The Chain of Thought (CoT) Router introduces a JSON parsing step and increases token count, adding ~200-500ms latency per query.
*   **Current Mitigation**: Using `fast` (Llama3-8b) model vs `strong` model.
*   **Future Optimization**:
    *   **Router Caching**: Cache the intent for identical queries (e.g., "Show me errors" is always SQL).
    *   **Distillation**: Fine-tune a tiny model (e.g., TinyLlama) specifically for this JSON classification task.

### B. Context Window Explosion
*   **Risk**: Strict Verification retrieves full raw log bodies. If 50+ logs are retrieved, we risk hitting the 8k/32k context limit, leading to truncation and False Negatives.
*   **Future Optimization**:
    *   **Summarizer Node**: Add an intermediate node to summarize retrieved logs before passing them to the Verifier or Synthesizer.
    *   **Dynamic Windowing**: Only fetch the first N characters of body, or use a "Snippet" view for verification.

### C. Ingestion Bottleneck
*   **Risk**: Smart Ingestion (2-Pass Table Scanning) is CPU/LLM intense. Ingesting large runbooks (50+ pages) may lag, though it occurs in the background.
*   **Future Optimization**:
    *   **Parallelization**: Run the "Discovery" pass and "Synthesis" pass on separate threads or queues.
    *   **Incremental Parsing**: Only re-parse changed sections of a runbook rather than the whole file.

## 2. Future Enhancements & Features 🚀

### A. Production Storage: Stateless S3 Architecture
*   **Goal**: Move away from stateful local DuckDB files for infinite scale.
*   **Design**:
    *   Logs shipped to S3 Parquet.
    *   LogPilot uses `duckdb_aws` extension to query S3 directly (`SELECT * FROM read_parquet('s3://...')`).
    *   **Benefit**: Zero-ETL, separation of storage and compute.

### B. Cloud-Native Mode (AWS CloudWatch)
*   **Goal**: Support users who don't want to move logs out of CloudWatch.
*   **Design**:
    *   Swap `SQLGenerator` for `InsightsGenerator`.
    *   Swap `DuckDBConnector` for `Boto3Connector`.
    *   **Benefit**: "Bring your own data" model.

### C. Storage Optimization: Log Normalization
*   **Goal**: Reduce storage cost for repetitive logs.
*   **Design**:
    *   Store `template_id` + `parameters` (JSON) instead of full text.
    *   Reconstruct messages on read.
    *   **Benefit**: 90% storage reduction for high-volume, repetitive log streams.

### D. User Feedback Loop (RLHF Lite)
*   **Goal**: Improve Router accuracy over time.
*   **Design**:
    *   Add "Thumbs Up/Down" to UI.
    *   If user corrects the agent (e.g., "No, I wanted a search, not SQL"), store this as a negative example.
    *   Inject these examples into the Router prompt dynamically.

### E. The Summarizer Agent
*   **Goal**: Prevent token overflow when using **Window Retrieval** (Gap 2 solution).
*   **The Issue**: Fetching windows (+/- 30s) per log multiplies context size by ~10x.
*   **Design**:
    *   **Trigger**: If `len(retrieved_context) > 4000 tokens`.
    *   **Action**: Invoke a lightweight LLM agent to "Compress" the logs into a summary.
    *   **Prompt**: "Read these 50 log lines. Summarize the timeline of failure. Remove noise."
    *   **Benefit**: Allows fetching 50+ matches without hitting the 8k limit of Llama 3.
