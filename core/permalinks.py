import base64
import json
import hmac
import hashlib
from typing import List, Dict, Any, Optional
from config.settings import settings
from core.models.schemas import CartItem

SECRET_KEY = getattr(settings, "PERMALINK_SECRET", "ucp-secret-key-v2026-08-25").encode()

def generate_permalink_token(items: List[Dict[str, Any]], currency: str = "USD") -> str:
    payload = {
        "items": items,
        "currency": currency,
        "v": "v2026-08-25"
    }
    raw_json = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
    b64_payload = base64.urlsafe_b64encode(raw_json).decode().rstrip("=")
    sig = hmac.new(SECRET_KEY, b64_payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{b64_payload}.{sig}"

def decode_permalink_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        b64_payload, received_sig = parts
        expected_sig = hmac.new(SECRET_KEY, b64_payload.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(received_sig, expected_sig):
            return None
        
        # Add padding
        rem = len(b64_payload) % 4
        if rem > 0:
            b64_payload += "=" * (4 - rem)
        raw_json = base64.urlsafe_b64decode(b64_payload.encode()).decode()
        return json.loads(raw_json)
    except Exception:
        return None