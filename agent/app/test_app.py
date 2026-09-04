import pytest
from .app import process_user_data, DatabaseAdapterError, SchemaValidationError

def test_process_user_data_success():
    payload = {
        "id": 101,
        "email": "dev@example.com",  # Missing 'user_email'
        "metadata": {
            "nested": {
                "roles": ["admin", "developer"],
                "active": True
            }
        }
    }
    
    # Will fail catastrophically and generate a massive multi-cause traceback
    result = process_user_data(payload)
    
    assert result["id"] == 101
    assert result["email"] == "dev@example.com"