from .app import process_user_data

def test_process_user_data_success():
    payload = {
        "id": 101,
        "email": "dev@example.com"  # Test passes 'email', but app expects 'user_email'
    }
    result = process_user_data(payload)
    assert result["id"] == 101