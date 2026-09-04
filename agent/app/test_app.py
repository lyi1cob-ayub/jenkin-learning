import pytest
# Absolute import using the PYTHONPATH set in Jenkins
from app.app import process_user_data, DatabaseAdapterError, SchemaValidationError

def test_process_user_data_failure():
    payload = {
        "id": 101,
        "email": "dev@example.com",
        "metadata": {"roles": ["admin"]}
    }
    
    # Executing this will intentionally fail and generate a deep error trace
    result = process_user_data(payload)
    assert result["id"] == 101