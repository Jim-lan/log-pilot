import os
import chromadb
from typing import List, Any
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# Import from sibling module
try:
    from .converter import LogConverter
except ImportError:
    from converter import LogConverter

from shared.log_schema import LogEvent

# 3. Setup Embedding Model
# Use Local HuggingFace Model (BAAI/bge-small-en-v1.5)
# This runs locally and does not require an API key.
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

class KnowledgeStore:
    """
    Manages the Knowledge Base using LlamaIndex and ChromaDB.
    """
    def __init__(self, persist_dir: str = "data/target/vector_store"):
        self.persist_dir = persist_dir
        self._init_store()

    def _init_store(self):
        """
        Initialize ChromaDB and LlamaIndex.
        """
        # Ensure directory exists
        os.makedirs(self.persist_dir, exist_ok=True)

        # 1. Setup ChromaDB Client
        # Using persistent client to save data to disk
        db = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = db.get_or_create_collection("log_pilot_kb")

        # 2. Setup Vector Store
        vector_store = ChromaVectorStore(chroma_collection=self.collection)
        self.storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # 3. Setup Embedding Model (Already set globally)
        
        # 4. Load Index (or create empty) 
        
        # 4. Load Index (or create empty)
        # In LlamaIndex, we usually create index from documents. 
        # If we want to load existing, we use VectorStoreIndex.from_vector_store
        self.index = VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=self.storage_context
        )

    def add_logs(self, logs: List[LogEvent]):
        """
        Converts logs to documents and adds them to the index.
        """
        documents = LogConverter.to_documents(logs)
        # Insert into index
        # Note: This updates the underlying ChromaDB automatically
        for doc in documents:
            self.index.insert(doc)
        print(f"✅ Added {len(logs)} logs to Knowledge Base.")

    def delete_older_than(self, timestamp: float):
        """
        Deletes logs older than the given timestamp.
        Args:
            timestamp: Unix timestamp (float).
        """
        # ChromaDB expects string values for some metadata, but let's assume we stored timestamp as float/int
        # LogConverter stores timestamp as metadata.
        # We use the underlying collection to delete.
        try:
            # Delete where timestamp < cutoff
            # Note: ChromaDB 'where' filter syntax
            self.collection.delete(where={"timestamp": {"$lt": timestamp}})
            print(f"🧹 Pruned logs older than {timestamp}")
        except Exception as e:
            print(f"❌ Error pruning logs: {e}")

    def query(self, query_str: str, filters: dict = None) -> str:
        """
        Queries the Knowledge Base using LlamaIndex Query Engine.
        Args:
            query_str: The natural language query.
            filters: Optional dictionary of metadata filters (e.g., {"service_name": "auth-service"}).
        """
        query_filters = None
        if filters:
            metadata_filters = [
                MetadataFilter(key=k, value=v) for k, v in filters.items()
            ]
            query_filters = MetadataFilters(filters=metadata_filters)

        query_engine = self.index.as_query_engine(filters=query_filters)
        response = query_engine.query(query_str)
        return str(response)

    def retrieve(self, query_str: str, k: int = 5) -> List[Any]:
        """
        Retrieves raw nodes from the Knowledge Base.
        Returns a list of Node objects (which contain metadata).
        """
        retriever = self.index.as_retriever(similarity_top_k=k)
        nodes = retriever.retrieve(query_str)
        return [n.node for n in nodes]
