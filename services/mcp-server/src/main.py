import sys
import os
import duckdb
import requests
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

# Ensure we can import shared modules
sys.path.append("/app")
from shared.db.duckdb_client import DuckDBConnector

# Initialize FastMCP
mcp = FastMCP("LogPilot")

# Initialize DB Client (Read-Only)
db_client = None

def get_db():
    global db_client
    if not db_client:
        db_client = DuckDBConnector(read_only=True)
    return db_client

@mcp.tool()
def query_logs(sql_query: str) -> str:
    """
    Executes a read-only SQL query against the logs database.
    """
    try:
        db = get_db()
        result = db.conn.execute(sql_query).fetchall()
        return str(result)
    except Exception as e:
        return f"Error executing SQL: {e}"

@mcp.tool()
def ask_log_pilot(question: str) -> str:
    """
    Asks the LogPilot AI Agent a natural language question.
    """
    try:
        response = requests.post(
            "http://pilot-orchestrator:8000/query",
            json={"query": question},
            timeout=60
        )
        response.raise_for_status()
        return response.json().get("answer", "No answer received.")
    except Exception as e:
        return f"Error calling Pilot: {e}"

@mcp.resource("logs://recent")
def get_recent_logs() -> str:
    """
    Returns the last 50 log entries.
    """
    try:
        db = get_db()
        result = db.conn.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 50").fetchall()
        return str(result)
    except Exception as e:
        return f"Error fetching recent logs: {e}"

@mcp.resource("logs://schema")
def get_schema() -> str:
    """
    Returns the schema of the logs table.
    """
    try:
        db = get_db()
        result = db.conn.execute("DESCRIBE logs").fetchall()
        return str(result)
    except Exception as e:
        return f"Error fetching schema: {e}"

# Expose as FastAPI app (FastMCP handles this internally if we ask it to)
# But to be explicit for uvicorn:
# FastMCP doesn't expose 'app' attribute directly in all versions.
# A safe bet is to use mcp.run() if it was a script, but for uvicorn we need an app object.
# Let's try to see if FastMCP has ._fastapi_app or similar, OR just use the standard library.

# RE-STRATEGY: Use standard mcp server + starlette/fastapi
# FastMCP is great but if I can't find the 'app' export, it's risky.
# However, recent FastMCP updates usually allow `mcp.mount(app)`.
# Let's assume `mcp` object IS the app or can be run. 

# Actually, let's look at the Dockerfile again. 
# CMD ["uvicorn", "src.main:app", ...]
# So I need an `app` object here.

# Let's try to create a FastAPI app and include the MCP router?
# Since I don't have the exact docs, I will use a pattern that is common:
# `app = FastAPI()`
# `mcp.mount(app)` (Hypothetical)

# SAFEST BET:
# Just return `mcp` and hope uvicorn can run it (unlikely).
# OR:
# Use `mcp` library's `Server` class and `SSE` transport manually.

# Let's stick to the code I wrote but add:
# `app = mcp._fastapi_app` if it exists?
# No, let's just use `mcp` as the object and change Dockerfile to `src.main:mcp`.
# FastMCP might implement ASGI.

# Wait, I'll check if I can find a reference.
# If not, I will use the `mcp-server-py` standard pattern.

# Let's assume FastMCP is NOT available or too new.
# I will use `mcp` standard server.

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route

server = Server("LogPilot")

# ... define handlers ...
# server.list_tools() ...

# This is getting complicated without docs.
# Let's go back to FastMCP. It is designed for this.
# I will assume `FastMCP` works.
# I will add `app = FastAPI()` and try to integrate.

# Actually, looking at `mcp` python SDK examples:
# `mcp = FastMCP("name")`
# `if __name__ == "__main__": mcp.run()`
# To run with uvicorn, maybe `app = mcp.fastapi_app`?

# I will leave `main.py` as is for now, but I will try to make it runnable.
# I will add `if __name__ == "__main__": mcp.run()`
# And for uvicorn, I will try to expose `app`.

# Let's just use `mcp` object in Dockerfile and see if it fails.
# If it fails, I'll fix it.

