FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY services/sentry/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code (Context is project root)
COPY . .

# Set python path
ENV PYTHONPATH=/app

# Run the sentry service
CMD ["python", "-u", "services/sentry/src/main.py"]
