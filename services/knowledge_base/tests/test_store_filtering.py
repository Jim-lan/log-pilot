import pytest
from unittest.mock import MagicMock, patch
from services.knowledge_base.src.store import KnowledgeStore
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter

@patch("services.knowledge_base.src.store.chromadb.PersistentClient")
@patch("services.knowledge_base.src.store.ChromaVectorStore")
@patch("services.knowledge_base.src.store.VectorStoreIndex")
@patch("services.knowledge_base.src.store.StorageContext")
def test_query_with_filters(mock_storage_context, mock_index_cls, mock_chroma_store, mock_chroma_client):
    # Setup Mocks
    mock_index_instance = MagicMock()
    mock_query_engine = MagicMock()
    mock_index_instance.as_query_engine.return_value = mock_query_engine
    mock_query_engine.query.return_value = "Filtered Answer"
    
    mock_index_cls.from_vector_store.return_value = mock_index_instance
    
    # Initialize Store
    store = KnowledgeStore(persist_dir="test_data")
    
    # Test query with filters
    filters = {"service_name": "auth-service", "severity": "ERROR"}
    response = store.query("What happened?", filters=filters)
    
    # Verify response
    assert response == "Filtered Answer"
    
    # Verify as_query_engine was called with filters
    # We need to check the arguments passed to as_query_engine
    args, kwargs = mock_index_instance.as_query_engine.call_args
    assert "filters" in kwargs
    passed_filters = kwargs["filters"]
    
    assert isinstance(passed_filters, MetadataFilters)
    assert len(passed_filters.filters) == 2
    
    # Check individual filters
    # Note: Order might vary, so we check existence
    filter_keys = [f.key for f in passed_filters.filters]
    filter_values = [f.value for f in passed_filters.filters]
    
    assert "service_name" in filter_keys
    assert "auth-service" in filter_values
    assert "severity" in filter_keys
    assert "ERROR" in filter_values
