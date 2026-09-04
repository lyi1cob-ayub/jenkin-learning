import sys
import traceback

class DatabaseAdapterError(Exception):
    """Raised when data serialization fails at the storage adapter level."""
    pass

class SchemaValidationError(Exception):
    """Raised when payload schema validation fails deeply."""
    pass

def _resolve_nested_attributes(data: dict, depth: int = 0):
    # Intentional deep recursion stack bloat
    if depth > 15:
        raise SchemaValidationError(f"Max schema traversal depth exceeded at depth {depth}")
    
    # Intentionally try to access an unhashable dict as a set element to crash Pytest
    cache_set = set()
    cache_set.add(data)  # TypeError: unhashable type: 'dict'
    
    return data

def _transform_payload(payload: dict):
    try:
        validated_data = _resolve_nested_attributes(payload)
        user_id = validated_data["id"]
        # KeyError here, but wrapped in nested context
        email = validated_data["user_email"]
        return {"id": user_id, "email": email}
    except KeyError as ke:
        raise KeyError(f"Missing mandatory mapping key: {ke}") from ke
    except TypeError as te:
        # Wrap and chain exception to blow up the traceback size
        raise DatabaseAdapterError("Failed to hash payload for caching layer") from te

def process_user_data(user_payload: dict):
    """
    Main processing entrypoint.
    Executes payload transformation across multi-layer validation pipeline.
    """
    try:
        return _transform_payload(user_payload)
    except Exception as exc:
        # Chained exception propagation across business boundaries
        raise RuntimeError(
            f"Fatal pipeline processing failure for payload payload_id={id(user_payload)}"
        ) from exc