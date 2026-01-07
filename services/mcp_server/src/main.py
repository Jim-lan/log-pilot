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



@mcp.tool()
def query_logs(sql_query: str) -> str:
    """
    Executes a read-only SQL query against the logs database.
    """
    try:
        db = DuckDBConnector(read_only=True)
        try:
            result = db.conn.execute(sql_query).fetchall()
            return str(result)
        finally:
            db.close()
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
        db = DuckDBConnector(read_only=True)
        try:
            result = db.conn.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 50").fetchall()
            return str(result)
        finally:
            db.close()
    except Exception as e:
        return f"Error fetching recent logs: {e}"

@mcp.resource("logs://schema")
def get_schema() -> str:
    """
    Returns the schema of the logs table.
    """
    try:
        db = DuckDBConnector(read_only=True)
        try:
            result = db.conn.execute("DESCRIBE logs").fetchall()
            return str(result)
        finally:
            db.close()
    except Exception as e:
        return f"Error fetching schema: {e}"

# End of file

