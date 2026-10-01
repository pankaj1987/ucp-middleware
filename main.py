import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.permalinks import decode_permalink_token
from core.models.schemas import CartItem

from config.settings import settings
from adapters.factory import get_commerce_adapter
from mock_gmc.engine import gmc_index
from agents.router import router as ucp_router
from core.models.schemas import Product
from typing import List

logger = logging.getLogger("ucp.main")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Prime local GMC index from Shopify adapter on server boot
    try:
        adapter = get_commerce_adapter()
        products = await adapter.search_products("", limit=20)
        if products:
            gmc_index.sync_catalog(products)
            logger.info(f"Loaded {len(products)} products into local GMC DuckDB catalog.")
    except Exception as e:
        logger.warning(f"Could not prime catalog on boot: {e}")
    yield

app = FastAPI(
    title="Google UCP Enterprise Commerce Middleware",
    description="Universal Commerce Protocol (UCP v2026-08-25) Autonomous Shopping Engine",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    session_id: str = Field(default="session-default")
    mode: str = Field(default="deterministic", description="gemini | deterministic")
    prompt: str

# 1. Primary Unified Multi-Agent Endpoint
@app.post("/api/v1/agent/chat", summary="Google UCP Unified Agent Endpoint")
async def chat_handler(req: ChatRequest):
    """
    Routes directly through GoogleUCPRouter.
    When mode='deterministic', bypasses all external LLM APIs (0 tokens).
    """
    logger.info(f"Incoming Chat Request: mode='{req.mode}', session_id='{req.session_id}'")
    try:
        response = await ucp_router.route(
            mode=req.mode,
            prompt=req.prompt,
            session_id=req.session_id
        )
        return response.model_dump()
    except Exception as e:
        logger.error(f"Execution Error in chat_handler: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/agent/session/{session_id}", summary="Fetch active session state")
async def session_handler(session_id: str):
    return ucp_router.get_session_state(session_id)

# 2. GMC Catalog Endpoints
@app.get("/mock-gmc/products", summary="List products in local GMC catalog")
async def list_gmc_products(query: str = Query("", description="Search term")):
    return gmc_index.query_catalog(query)

@app.post("/mock-gmc/sync", summary="Re-index Catalog from Commerce Adapter")
async def sync_gmc_catalog():
    adapter = get_commerce_adapter()
    prods = await adapter.search_products("", limit=100)
    gmc_index.sync_catalog(prods)
    return {"status": "success", "indexed_items_count": len(prods)}

@app.post("/mock-gmc/index-products", summary="Manually Push Products to GMC Index")
async def index_custom_products(products: List[Product]):
    gmc_index.insert_products(products)
    return {"status": "success", "inserted": len(products)}

@app.post("/mock-gmc/upload-xml", summary="Upload and Index GMC XML Feed")
async def upload_gmc_xml(file: UploadFile = File(...)):
    content = await file.read()
    count = gmc_index.ingest_gmc_xml(content)
    return {"status": "success", "ingested": count}

@app.get("/mock-gmc/inspect", summary="Debug Inspection for DuckDB Tables")
async def inspect_duckdb(query: str = Query("SELECT * FROM gmc_products", description="SQL query")):
    try:
        return gmc_index.run_debug_query(query)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



class ActionResolveRequest(BaseModel):
    session_id: str
    challenge_id: str
    otp_code: str = "123456"

@app.get("/cart/recover", summary="Hydrate Cart from UCP Shopping Permalink (#523)")
async def recover_cart_permalink(token: str = Query(..., description="UCP Permalink Token")):
    """Stateless recovery of cart items from signed permalink."""
    payload = decode_permalink_token(token)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid or tampered permalink token.")

    adapter = get_commerce_adapter()
    items = [CartItem(**i) for i in payload.get("items", [])]
    cart = await adapter.create_cart(items)
    
    return {
        "status": "hydrated",
        "cart": cart.model_dump(),
        "recovery_source": "UCP_Shopping_Permalink_v2026-08-25"
    }

@app.post("/api/v1/ucp/actions/resolve", summary="Resolve Vendor-Agnostic 3DS2 Action Challenge")
async def resolve_action_endpoint(req: ActionResolveRequest):
    """Submits 3DS2 OTP resolution and moves checkout to completed."""
    try:
        order = await ucp_router.resolve_action_challenge(
            session_id=req.session_id,
            challenge_id=req.challenge_id,
            otp_code=req.otp_code
        )
        return {
            "status": "challenge_resolved",
            "order": order
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/healthz")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}