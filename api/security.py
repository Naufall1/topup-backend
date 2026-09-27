from config import config
from hashlib import md5

def sign_request(payload: str) -> str:
    data = f"{config.USERNAME}{config.API_KEY}{payload}"
    return md5(data.encode()).hexdigest()