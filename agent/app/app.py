class DatabaseAdapterError(Exception):
    """Raised when data serialization fails at the storage adapter level."""
    pass

class SchemaValidationError(Exception):
    """Raised when payload schema validation fails deeply."""
    pass

def _resolve_nested_attributes(data: dict, depth: int = 0):
    if depth > 15:
        raise SchemaValidationError(f"Max schema traversal depth exceeded at depth {depth}")
    
    # Intentionally try to add an unhashable dict to a set to raise a TypeError
    cache_set = set()
    cache_set.add(data) 
    return data

def _transform_payload(payload: dict):
    try:
        validated_data = _resolve_nested_attributes(payload)
        user_id = validated_data["id"]
        email = validated_data["user_email"]
        return {"id": user_id, "email": email}
    except KeyError as ke:
        raise KeyError(f"Missing mandatory mapping key: {ke}") from ke
    except TypeError as te:
        raise DatabaseAdapterError("Failed to hash payload for caching layer") from te

def process_user_data(user_payload: dict):
    """Main execution function that triggers chained exceptions."""
    try:
        return _transform_payload(user_payload)
    except Exception as exc:
        raise RuntimeError(
            f"Fatal pipeline processing failure for payload_id={id(user_payload)}"
        ) from exc