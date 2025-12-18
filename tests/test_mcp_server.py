import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root and mcp src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../services/mcp-server/src")))

# Mock shared dependencies
sys.modules["shared.db.duckdb_client"] = MagicMock()

# Mock 'mcp' package entirely since it's not installed locally
mock_mcp_pkg = MagicMock()
sys.modules["mcp"] = mock_mcp_pkg
sys.modules["mcp.server"] = MagicMock()
sys.modules["mcp.server.fastmcp"] = MagicMock()

# Configure FastMCP mock to return identity decorators
# This ensures that @mcp.tool() doesn't replace the function with a Mock
mock_fastmcp = MagicMock()
mock_fastmcp.tool.return_value = lambda func: func
mock_fastmcp.resource.return_value = lambda func: func
# When FastMCP("LogPilot") is called, it returns this configured mock
sys.modules["mcp.server.fastmcp"].FastMCP.return_value = mock_fastmcp

# Mock FastAPI
sys.modules["fastapi"] = MagicMock()

# Import functions to test
from services.mcp_server.src.main import query_logs, ask_log_pilot, get_recent_logs, get_db

@patch("services.mcp_server.src.main.DuckDBConnector")
def test_query_logs(mock_connector):
    # Setup Mock DB
    mock_db_instance = MagicMock()
    mock_connector.return_value = mock_db_instance
    mock_db_instance.conn.execute.return_value.fetchall.return_value = [("error1",), ("error2",)]
    
    # Reset global db_client in main to force re-init
    import services.mcp_server.src.main as main_module
    main_module.db_client = None
    
    # Run Tool
    result = query_logs("SELECT * FROM logs")
    
    # Verify
    assert "error1" in result
    assert "error2" in result
    mock_db_instance.conn.execute.assert_called_with("SELECT * FROM logs")

@patch("services.mcp_server.src.main.requests.post")
def test_ask_log_pilot(mock_post):
    # Setup Mock Response
    mock_response = MagicMock()
    mock_response.json.return_value = {"answer": "The answer is 42."}
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    
    # Run Tool
    result = ask_log_pilot("What is the meaning of life?")
    
    # Verify
    assert result == "The answer is 42."
    mock_post.assert_called_once()
