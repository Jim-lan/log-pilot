from typing import List, Dict, Any
from llama_index.core import Document
from shared.log_schema import LogEvent

class LogConverter:
    """
    Converts LogPilot LogEvent objects into LlamaIndex Documents.
    """
    
    @staticmethod
    def to_document(log: LogEvent) -> Document:
        """
        Converts a single LogEvent to a Document.
        The text content combines the timestamp, service, severity, and body.
        Metadata includes the structured fields for filtering.
        """
        # Construct a rich text representation for the embedding model
        text_content = (
            f"Timestamp: {log.timestamp}\n"
            f"Service: {log.service_name}\n"
            f"Severity: {log.severity}\n"
            f"Message: {log.body}\n"
            f"Context: {log.context}"
        )
        
        # Metadata for filtering (e.g., "Give me errors from auth-service")
        metadata = {
            "timestamp": str(log.timestamp),
            "service_name": log.service_name,
            "severity": log.severity,
            **log.context  # Flatten context into metadata for easier filtering
        }
        
        return Document(
            text=text_content,
            metadata=metadata,
            excluded_llm_metadata_keys=["timestamp"], # Don't distract LLM with raw timestamp string if not needed
            excluded_embed_metadata_keys=["timestamp"] 
        )

    @staticmethod
    def to_documents(logs: List[LogEvent]) -> List[Document]:
        return [LogConverter.to_document(log) for log in logs]
