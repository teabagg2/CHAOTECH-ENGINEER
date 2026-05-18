from jose import jwt
from datetime import datetime, timedelta

SECRET = "astra_secret_key"

def create_token(email):
    payload = {
        "sub": email,
        "exp": datetime.utcnow() + timedelta(hours=2)
    }

    return jwt.encode(payload, SECRET, algorithm="HS256")