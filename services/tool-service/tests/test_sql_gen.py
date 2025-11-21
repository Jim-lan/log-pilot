import pytest
from unittest.mock import MagicMock
import sys
import os

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.tool_service.src.sql_gen import SQLGenerator

@pytest.fixture
def mock_db():
    return MagicMock()

def test_generate_sql_count_errors(mock_db):
    """Test that 'count errors' generates the correct SQL."""
    # Arrange
    generator = SQLGenerator()
    generator.db = mock_db
    query = "Count all errors"
    
    # Act
    sql = generator.generate_sql(query)
    
    # Assert
    assert "SELECT count(*)" in sql
    assert "severity='ERROR'" in sql

def test_execute_sql_success(mock_db):
    """Test that execute() calls the DB connector correctly."""
    # Arrange
    generator = SQLGenerator()
    generator.db = mock_db
    mock_db.query.return_value = [(10,)]
    
    # Act
    result = generator.execute("Count errors")
    
    # Assert
    mock_db.query.assert_called_once()
    assert result == [(10,)]
