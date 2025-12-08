FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install fastapi uvicorn

# Copy source code
COPY . .

# Set python path
ENV PYTHONPATH=/app

# Run the API
CMD ["uvicorn", "services.pilot_orchestrator.src.api:app", "--host", "0.0.0.0", "--port", "8000"]
