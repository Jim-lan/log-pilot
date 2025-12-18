import sys
import os

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import mcp

if __name__ == "__main__":
    # Run the MCP server using FastMCP's built-in runner
    # Note: FastMCP.run() arguments might vary by version, but usually supports transport/port.
    # If not, we will find out.
    print("🚀 Starting LogPilot MCP Server...")
    mcp.run(transport='sse', port=8001, host='0.0.0.0')
