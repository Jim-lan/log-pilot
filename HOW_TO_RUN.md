# 🚀 How to Run LogPilot V2

This guide provides step-by-step instructions to set up, run, and test the LogPilot V2 system.

## 📋 Prerequisites
- **Python 3.9+**
- **Pip**
- **Git**
- **API Keys**:
    - `OPENAI_API_KEY` (if using OpenAI)
    - `GEMINI_API_KEY` (if using Google Gemini)
    - *Optional*: `LOCAL_API_KEY` (if using a local LLM server)

## 🛠️ Installation

1.  **Clone the repository** (if you haven't already):
    ```bash
    git clone <repo-url>
    cd log-pilot
    ```

2.  **Create a Virtual Environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

1.  **Set Environment Variables**:
    ```bash
    export OPENAI_API_KEY="sk-..."
    export GEMINI_API_KEY="AIza..."
    ```

2.  **LLM Configuration**:
    - Edit `config/llm_config.yaml` to switch between `openai`, `gemini`, or `local`.
    - Default is `openai`.

## 🏃‍♂️ Running the System

### 1. Run the API Gateway (The Core)
This starts the REST API that exposes the Pilot Orchestrator.

```bash
python3 services/api_gateway/src/main.py
```
- **URL**: `http://localhost:8000`
- **Docs**: `http://localhost:8000/docs`

### 2. Run the Benchmark (Local vs. Cloud)
Compare the performance of your Local LLM against the Cloud.

```bash
python3 scripts/compare_models.py
```

### 3. Run the Ingestion Worker (Mock)
Simulate log ingestion from Kafka.

```bash
python3 services/ingestion-worker/src/main.py
```

## 🧪 Testing

### Run Unit Tests
```bash
python3 -m pytest
```

### Run End-to-End Test
```bash
./scripts/e2e_test.sh
```

## 📂 Key Files
- **`data/system_catalog.csv`**: The business logic mapping (Service -> Department).
- **`docs/walkthrough.md`**: Detailed project walkthrough and architecture summary.
