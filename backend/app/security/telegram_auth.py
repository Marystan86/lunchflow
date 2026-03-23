import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from fastapi import HTTPException


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict:
    if not init_data or not bot_token:
        raise HTTPException(status_code=401, detail="invalid telegram auth data")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="invalid telegram auth data")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items(), key=lambda item: item[0]))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=401, detail="invalid telegram auth data")

    user_raw = pairs.get("user")
    if not user_raw:
        raise HTTPException(status_code=401, detail="invalid telegram auth data")

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=401, detail="invalid telegram auth data") from exc

    if "id" not in user:
        raise HTTPException(status_code=401, detail="invalid telegram auth data")

    return {
        "id": int(user["id"]),
        "username": user.get("username"),
        "first_name": user.get("first_name") or "",
        "last_name": user.get("last_name") or "",
        "photo_url": user.get("photo_url"),
    }
