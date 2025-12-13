FROM python:3.9-slim

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
COPY services/mcp-server/src /app/src

# Expose port for SSE
EXPOSE 8001

# Run the MCP server using mcp CLI
CMD ["mcp", "run", "src.main:mcp", "--transport", "sse", "--port", "8001", "--host", "0.0.0.0"]
