import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from shared.log_schema import LogEvent
from services.knowledge_base.src.store import KnowledgeStore

@pytest.fixture
def mock_log_event():
    return LogEvent(
        timestamp=datetime.now(),
        severity="ERROR",
        service_name="test-service",
        body="Test error message",
        context={"user_id": "123"}
    )

@patch("services.knowledge_base.src.store.chromadb.PersistentClient")
@patch("services.knowledge_base.src.store.ChromaVectorStore")
@patch("services.knowledge_base.src.store.VectorStoreIndex")
@patch("services.knowledge_base.src.store.StorageContext")
def test_add_logs(mock_storage_context, mock_index_cls, mock_chroma_store, mock_chroma_client, mock_log_event):
    # Setup Mocks
    mock_index_instance = MagicMock()
    mock_index_cls.from_vector_store.return_value = mock_index_instance
    
    # Initialize Store
    store = KnowledgeStore(persist_dir="test_data")
    
    # Test add_logs
    store.add_logs([mock_log_event])
    
    # Verify insert was called
    assert mock_index_instance.insert.called
    # Verify it was called once for one log
    assert mock_index_instance.insert.call_count == 1

@patch("services.knowledge_base.src.store.chromadb.PersistentClient")
@patch("services.knowledge_base.src.store.ChromaVectorStore")
@patch("services.knowledge_base.src.store.VectorStoreIndex")
@patch("services.knowledge_base.src.store.StorageContext")
def test_query(mock_storage_context, mock_index_cls, mock_chroma_store, mock_chroma_client):
    # Setup Mocks
    mock_index_instance = MagicMock()
    mock_query_engine = MagicMock()
    mock_index_instance.as_query_engine.return_value = mock_query_engine
    mock_query_engine.query.return_value = "Mock Answer"
    
    mock_index_cls.from_vector_store.return_value = mock_index_instance
    
    # Initialize Store
    store = KnowledgeStore(persist_dir="test_data")
    
    # Test query
    response = store.query("What happened?")
    
    # Verify response
    assert response == "Mock Answer"
    mock_query_engine.query.assert_called_with("What happened?")
