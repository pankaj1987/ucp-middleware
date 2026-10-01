import json
from pathlib import Path
from fastapi import APIRouter, Response
from config.settings import settings

router = APIRouter(tags=["UCP Discovery"])

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "config" / "ucp_manifest.json"

def load_manifest() -> dict:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Dynamically inject base host from settings
    base = settings.BASE_URL
    services = data["ucp"]["services"]
    services["dev.ucp.shopping"]["endpoints"]["rest"] = f"{base}/api/v1/ucp/shopping"
    services["dev.ucp.shopping"]["endpoints"]["mcp_sse"] = f"{base}/mcp/sse"
    services["dev.ucp.actions"]["endpoints"]["rest"] = f"{base}/api/v1/ucp/actions"
    data["ucp"]["auth"]["agent_registration_uri"] = f"{base}/api/v1/auth/agent"
    return data

@router.get("/.well-known/ucp.json", summary="UCP Canonical Discovery Manifest")
@router.get("/.well-known/ucp", summary="UCP Discovery Fallback")
async def get_ucp_manifest():
    manifest_data = load_manifest()
    return Response(
        content=json.dumps(manifest_data, indent=2),
        media_type="application/json",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
            "X-UCP-Version": "2026-08-25"
        }
    )