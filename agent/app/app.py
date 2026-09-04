def process_user_data(user_payload: dict):
    # Expecting keys "id" and "email", but access a key that doesn't exist
    user_id = user_payload["id"]
    email = user_payload["user_email"]  # Missing key error
    return {"id": user_id, "email": email}