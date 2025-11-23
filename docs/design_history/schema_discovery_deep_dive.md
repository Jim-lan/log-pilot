# 🕵️ Schema Discovery: Deep Dive & Analysis

## 1. Current Implementation
We have built a **Self-Correcting Agent** that uses Generative AI to write code (Regex) for us.

*   **Generator (`src/generator.py`)**: Uses an LLM (abstracted) to look at log samples and write a Python Regex pattern. It is prompted to use *Named Groups* (e.g., `(?P<timestamp>...)`).
*   **Validator (`src/validator.py`)**: A deterministic code block that compiles the generated regex and tests it against *all* provided samples.
    *   *Improvement*: We just updated this to **reject** regexes that don't capture any fields (preventing lazy `.*` matches).
*   **Agent (`src/agent.py`)**: The orchestrator that runs the loop: `Generate -> Validate -> Retry`.

## 2. The Discovery Process
1.  **Sampling**: We take 5-10 representative log lines from a new, unknown service.
2.  **Drafting**: The LLM guesses a pattern.
3.  **Testing**: We verify the pattern works on *all* samples.
4.  **Deployment**: Once verified, this Regex is saved (to be implemented) and used by the **Ingestion Worker** for high-speed parsing.

## 3. What's Next?
*   **Registry Integration**: We need a place to store these discovered schemas. A `SchemaRegistry` (Database or YAML file) mapping `service_name -> regex_pattern`.
*   **Dynamic Loading**: The Ingestion Worker needs to load these patterns on the fly. When it sees a log from `payment-service`, it should look up the specific regex rather than using a generic one.

## 4. Alternative Approaches
| Approach | Pros | Cons |
| :--- | :--- | :--- |
| **Pure LLM Parsing** | Extremely flexible, handles any format. | **Too Slow & Expensive**. You can't run an LLM for every single log line at 10k logs/sec. |
| **Grok (Logstash)** | Industry standard, huge library of patterns. | **Manual**. Requires a human to find and configure the right pattern. Hard to automate. |
| **Clustering (Drain3)** | Great for finding templates. | **No Semantics**. It finds the structure but doesn't know that "10.0.0.1" is an `ip_address` or "user_123" is a `user_id`. |
| **Hybrid (Our Approach)** | **Best of Both**. LLM understands semantics ("this looks like an IP") and writes a fast Regex for the heavy lifting. | Complexity of the feedback loop. |

## 5. Concerns & Risks
*   **Schema Drift**: If the developer changes the log format slightly, the Regex will break.
    *   *Mitigation*: The Ingestion Worker should detect high failure rates and trigger the Discovery Agent to "re-learn" the schema automatically.
*   **ReDoS (Regex Denial of Service)**: Poorly written regexes can cause CPU spikes.
    *   *Mitigation*: We should add a timeout to the regex execution or use a safe regex engine (like `google/re2`) in production.
*   **Ambiguity**: Different logs from the same service might look vastly different.
    *   *Mitigation*: We might need multiple regexes per service, or a more flexible grammar.
