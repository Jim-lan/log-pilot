from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class LogEvent(BaseModel):
    """
    The Golden Standard Log Event.
    All raw logs must be transformed into this structure.
    """
    timestamp: datetime = Field(..., description="The timestamp of the log event")
    severity: str = Field(..., description="Log level (INFO, ERROR, WARN, DEBUG)")
    service_name: str = Field(..., description="Name of the service that generated the log")
    trace_id: Optional[str] = Field(None, description="Distributed trace ID if available")
    body: str = Field(..., description="The raw log message or template")
    
    # Standard Resource Attributes (Metadata)
    environment: Optional[str] = Field(None, description="Deployment environment (prod, staging, dev)")
    app_id: Optional[str] = Field(None, description="Unique application identifier")
    department: Optional[str] = Field(None, description="Owner department")
    host: Optional[str] = Field(None, description="Hostname or IP address")
    region: Optional[str] = Field(None, description="Cloud region or datacenter")

    context: Dict[str, Any] = Field(default_factory=dict, description="Dynamic JSON context fields")

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2023-10-27T10:00:00Z",
                "severity": "ERROR",
                "service_name": "payment-service",
                "trace_id": "abc-123",
                "body": "Payment failed for user 123",
                "environment": "production",
                "app_id": "com.example.payment",
                "department": "finance",
                "context": {"user_id": 123, "error_code": "PAY_001"}
            }
        }
