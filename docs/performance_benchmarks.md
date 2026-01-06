# Performance Benchmarks 🚀

## Overview
These benchmarks reflect the system's performance using **Llama 3 (8B)** running locally on a MacBook Pro (M1/M2/M3 class).

## 1. Accuracy Metrics

Based on the "Golden Dataset" (20 test cases):

| Metric | Score | Description |
| :--- | :--- | :--- |
| **Intent Classification** | **100%** | Correctly distinguishes between SQL, RAG, and Ambiguous queries. |
| **SQL Syntax Validity** | **100%** | Generated SQL is executable by DuckDB. |
| **SQL Logic Accuracy** | **~90%** | Correctly answers the user's question (after guardrails). |
| **Hallucination Rate** | **Low** | Reduced significantly by "Balanced Prompt" strategy. |

### Key Improvements
-   **Guardrails**: The "Self-Correction Loop" catches 100% of missing `GROUP BY` clauses.
-   **Prompt Tuning**: Diversified examples reduced overfitting (copying specific service names) to near zero.

## 2. Latency Metrics

| Component | Average Latency | Notes |
| :--- | :--- | :--- |
| **Intent Classification** | ~2s | Fast, uses simplified prompt. |
| **SQL Generation** | ~5-10s | Depends on schema complexity. |
| **SQL Validation (Dry Run)** | <1s | Very fast (DuckDB `EXPLAIN`). |
| **SQL Fix Loop (if needed)** | ~10s per retry | Adds significant latency if initial SQL is bad. |
| **Total End-to-End** | **~15-20s** | Acceptable for complex analytical queries. |

## 3. Resource Usage

| Container | Memory | CPU |
| :--- | :--- | :--- |
| `pilot-orchestrator` | ~200MB | Low (mostly idle waiting for LLM). |
| `ingestion-worker` | ~150MB | Low (unless processing massive logs). |
| `frontend` | ~20MB | Negligible. |
| `ollama` (LLM) | ~6-8GB | High (requires dedicated VRAM/RAM). |

## 4. Recommendations for Production
-   **GPU**: A dedicated GPU (NVIDIA or Apple Silicon) is required for acceptable latency.
-   **Model**: Llama 3 8B is the minimum recommended. For higher accuracy, consider Llama 3 70B (requires ~40GB VRAM).
