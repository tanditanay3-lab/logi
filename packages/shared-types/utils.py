"""
Utility functions for Lanework shared types.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Optional


# ID prefixes for different entity types
ID_PREFIXES = {
    "agent_task": "task",
    "approval_request": "approval",
    "conversation": "conv",
    "voice_call": "call",
    "shipment": "shipment",
    "inventory_item": "inventory",
    "route": "route",
    "warehouse_task": "task",
    "driver": "driver",
    "vehicle": "vehicle",
    "forecast": "forecast",
    "quote": "quote",
    "carrier": "carrier",
    "webhook_event": "evt",
    "tenant": "tenant",
    "user": "user",
}


def generate_id(prefix: str = "") -> str:
    """
    Generate a unique ID with optional prefix.
    
    Args:
        prefix: Optional prefix for the ID (e.g., 'task', 'shipment')
        
    Returns:
        Unique ID string
    """
    unique_id = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID for shorter IDs
    if prefix:
        return f"{prefix}_{unique_id}"
    return unique_id


def generate_entity_id(entity_type: str) -> str:
    """
    Generate an ID for a specific entity type.
    
    Args:
        entity_type: The type of entity (e.g., 'agent_task', 'shipment')
        
    Returns:
        Unique ID with appropriate prefix
    """
    prefix = ID_PREFIXES.get(entity_type, "")
    return generate_id(prefix)


def get_current_timestamp() -> datetime:
    """
    Get current UTC timestamp.
    
    Returns:
        Current datetime in UTC
    """
    return datetime.now(timezone.utc)


def validate_tenant_id(tenant_id: str) -> bool:
    """
    Validate a tenant ID format.
    
    Args:
        tenant_id: The tenant ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Tenant IDs should be UUIDs or follow the pattern tenant_<uuid>
    pattern = r"^(tenant_[a-f0-9]{8}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}|[a-f0-9]{32})$"
    return bool(re.match(pattern, tenant_id, re.IGNORECASE))


def sanitize_string(value: str, max_length: int = 10000) -> str:
    """
    Sanitize a string value for storage.
    
    Args:
        value: The string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not value:
        return ""
    
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
    
    # Truncate to max length
    return sanitized[:max_length]


def format_reasoning_trace(reasoning: str, max_length: int = 50000) -> str:
    """
    Format reasoning trace for storage.
    
    Args:
        reasoning: The reasoning text
        max_length: Maximum allowed length
        
    Returns:
        Formatted reasoning trace
    """
    return sanitize_string(reasoning, max_length)


def get_entity_type_from_id(entity_id: str) -> Optional[str]:
    """
    Extract entity type from an ID.
    
    Args:
        entity_id: The entity ID
        
    Returns:
        Entity type if prefix is recognized, None otherwise
    """
    # Reverse the ID_PREFIXES mapping
    for entity_type, prefix in ID_PREFIXES.items():
        if entity_id.startswith(f"{prefix}_"):
            return entity_type
    return None


def parse_iso8601_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Parse an ISO8601 timestamp string.
    
    Args:
        timestamp_str: The timestamp string
        
    Returns:
        Parsed datetime or None if invalid
    """
    try:
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


def format_iso8601_timestamp(dt: datetime) -> str:
    """
    Format a datetime as ISO8601 string.
    
    Args:
        dt: The datetime to format
        
    Returns:
        ISO8601 formatted string
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
