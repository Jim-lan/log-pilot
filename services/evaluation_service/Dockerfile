FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for DuckDB and Ragas
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Ragas has many dependencies, so we pin versions to avoid conflicts
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn==0.27.0 \
    requests==2.31.0 \
    duckdb==0.9.2 \
    pandas==2.2.0 \
    ragas==0.0.22 \
    langchain==0.1.0 \
    langchain-community==0.0.13 \
    langchain-openai==0.0.2 \
    datasets==2.16.1

# Copy source code
COPY services/evaluation_service/src/ /app/src/
# Copy shared modules (if any needed, but trying to keep decoupled)
# For now, we assume evaluation service is self-contained or accesses data via API

# Expose port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
