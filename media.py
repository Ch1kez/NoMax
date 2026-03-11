from datetime import datetime, timedelta
from typing import Optional

from jose import jwt


class LiveKitConfig:
    def __init__(self, api_key: str, api_secret: str, host: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.host = host.rstrip("/")


def get_livekit_config_from_env() -> LiveKitConfig:
    import os

    api_key = os.getenv("LIVEKIT_API_KEY", "devkey")
    api_secret = os.getenv("LIVEKIT_API_SECRET", "devsecret")
    host = os.getenv("LIVEKIT_HOST", "wss://example.livekit.cloud")
    return LiveKitConfig(api_key=api_key, api_secret=api_secret, host=host)


def build_livekit_access_token(
    identity: str,
    room_name: str,
    ttl_seconds: int = 60 * 60,
) -> str:
    cfg = get_livekit_config_from_env()
    now = int(datetime.utcnow().timestamp())
    payload = {
        "sub": cfg.api_key,
        "iss": cfg.api_key,
        "iat": now,
        "exp": now + ttl_seconds,
        "video": {
            "room": room_name,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
        },
        "jti": f"{identity}-{room_name}-{now}",
    }
    token = jwt.encode(payload, cfg.api_secret, algorithm="HS256")
    return token

