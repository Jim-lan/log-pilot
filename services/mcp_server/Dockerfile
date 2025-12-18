FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared code
COPY shared /app/shared

# Copy service code
COPY services/mcp_server/src /app/src

# Expose port for SSE
EXPOSE 8001

# Run the MCP server using python script
CMD ["python", "src/run.py"]
