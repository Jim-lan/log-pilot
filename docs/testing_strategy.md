# LogPilot Testing Strategy

To ensure enterprise-grade reliability, we adopt a standardized testing pyramid approach.

## 1. Testing Levels

### 1.1 Unit Tests (`services/<service>/tests/`)
*   **Scope**: Individual functions and classes.
*   **Mocking**: ALL external dependencies (DB, LLM APIs, Kafka) must be mocked.
*   **Tool**: `pytest`
*   **Goal**: Verify logic correctness and edge cases.

### 1.2 Integration Tests (`tests/integration/`)
*   **Scope**: Interaction between two components (e.g., Agent -> Tool Service).
*   **Mocking**: Minimal. Use real DuckDB (in-memory) but mock expensive LLM calls.
*   **Goal**: Verify contract adherence and data flow.

### 1.3 End-to-End (E2E) Tests (`tests/e2e/`)
*   **Scope**: Full user flow (User Query -> Final Answer).
*   **Mocking**: None (or strictly controlled replay).
*   **Goal**: Verify system behavior in a production-like environment.

## 2. Standardized Test Structure

All test files must follow this naming convention: `test_<module_name>.py`.

### Example: Unit Test for SQLGenerator

```python
# services/tool-service/tests/test_sql_gen.py
import pytest
from unittest.mock import MagicMock
from src.sql_gen import SQLGenerator

@pytest.fixture
def mock_db():
    return MagicMock()

def test_generate_sql_count_errors(mock_db):
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
    # Arrange
    generator = SQLGenerator()
    generator.db = mock_db
    mock_db.query.return_value = [(10,)]
    
    # Act
    result = generator.execute("Count errors")
    
    # Assert
    mock_db.query.assert_called_once()
    assert result == [(10,)]
```

### Example: Integration Test (Agent -> Tool)

```python
# tests/integration/test_agent_tool_flow.py
import pytest
from services.pilot_orchestrator.src.agent import LogPilotAgent

def test_agent_routes_to_sql_tool():
    # Arrange
    agent = LogPilotAgent() # Uses real SQLGenerator
    
    # Act
    response = agent.process_query("Count errors")
    
    # Assert
    assert response["tool"] == "SQLGenerator"
    assert "result" in response
```

## 3. CI/CD Integration
Tests will be run automatically on every Pull Request.

```yaml
# .github/workflows/test.yml
steps:
  - name: Run Unit Tests
    run: pytest services/
  
  - name: Run Integration Tests
    run: pytest tests/integration/
```
