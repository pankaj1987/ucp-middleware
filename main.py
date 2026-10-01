from fastapi import FastAPI, HTTPException, Response, UploadFile, File, Query
from mock_gmc.engine import gmc_index

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from config.settings import settings
from adapters.factory import get_commerce_adapter
from agents.graph import get_compiled_graph, pg_pool
from api.discovery import router as discovery_router
from typing import List
from core.models.schemas import Product
from agents.gemini_agent import gemini_agent

class NativeAgentRequest(BaseModel):
    prompt: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Prime local GMC index
    adapter = get_commerce_adapter()
    products = await adapter.search_products("", limit=20)
    gmc_index.sync_catalog(products)
    
    # 2. Initialize LangGraph & PostgreSQL checkpointer tables
    await get_compiled_graph()
    
    yield
    
    # 3. Graceful shutdown: check .closed instead of .opened
    if not pg_pool.closed:
        await pg_pool.close()

app = FastAPI(
    title="UCP Enterprise Middleware",
    version="2026-08-25",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Discovery Router for /.well-known/ucp.json & /.well-known/ucp
app.include_router(discovery_router)


@app.post("/api/v1/agent/native-gemini", summary="Direct Native Google GenAI Agent with UCP Tools")
async def native_gemini_chat(req: NativeAgentRequest):
    """Executes user prompt directly with Google GenAI SDK without LangGraph wrapper."""
    try:
        result = await gemini_agent.chat(req.prompt)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Storefront root link discovery
@app.get("/", summary="Root Storefront Discovery Entry")
async def root():
    html_content = f"""
    <!DOCTYPE html>
    <html>
      <head>
        <title>UCP Storefront Gateway</title>
        <link rel="commerce-protocol" type="application/json" href="{settings.BASE_URL}/.well-known/ucp.json">
      </head>
      <body>
        <h1>UCP Enterprise Store Gateway</h1>
        <p>Discovery available at <a href="/.well-known/ucp.json">/.well-known/ucp.json</a></p>
      </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")

# 3. LangGraph Agent Chat Endpoint
class ChatRequest(BaseModel):
    session_id: str
    prompt: str

@app.post("/api/v1/agent/chat")
async def agent_chat(req: ChatRequest):
    graph = await get_compiled_graph()
    config = {"configurable": {"thread_id": req.session_id}}
    
    try:
        final_state = await graph.ainvoke(
            {"messages": [("user", req.prompt)]},
            config=config
        )
        last_message = final_state["messages"][-1]
        
        # Collect executed tool invocations for inspectability
        tool_events = []
        for msg in final_state["messages"]:
            if msg.type == "tool":
                tool_events.append({"tool": msg.name, "result": msg.content})

        return {
            "session_id": req.session_id,
            "response": last_message.content,
            "tool_history": tool_events
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 1. Standard GMC JSON Content API Endpoint
@app.get("/mock-gmc/products", summary="Google Merchant Center Content API Simulator")
async def get_mock_gmc_feed(query: str = "", limit: int = 50):
    products = gmc_index.query_catalog(query=query, limit=limit)
    return {
        "kind": "content#productsListResponse",
        "total": len(products),
        "resources": products
    }

# 2. Trigger On-Demand Catalog Sync from Shopify/Store Adapter
@app.post("/mock-gmc/sync", summary="Re-index Catalog from Commerce Adapter")
async def trigger_gmc_sync():
    adapter = get_commerce_adapter()
    products = await adapter.search_products("", limit=100)
    if products:
        gmc_index.sync_catalog(products)
    else:
        # Fall back to default seed if adapter search returns empty
        gmc_index.seed_default_catalog()
    
    total = len(gmc_index.query_catalog("", limit=1000))
    return {"status": "success", "indexed_items_count": total}

# 3. Direct Feed Ingestion Endpoint (Insert Custom Catalog Data)
@app.post("/mock-gmc/index-products", summary="Manually Push Products to GMC Index")
async def index_custom_products(products: List[Product]):
    gmc_index.insert_products(products)
    return {
        "status": "success",
        "inserted": len(products),
        "total": len(gmc_index.query_catalog("", limit=1000))
    }

# 4. Standard Google RSS 2.0 XML Feed Endpoint
@app.get("/mock-gmc/feed.xml", summary="Google Merchant Center XML RSS Feed")
async def get_gmc_xml_feed():
    products = gmc_index.query_catalog("", limit=100)
    xml_items = []
    for p in products:
        xml_items.append(f"""
        <item>
            <g:id>{p['id']}</g:id>
            <title><![CDATA[{p['title']}]]></title>
            <description><![CDATA[{p['description']}]]></description>
            <link>{p['link']}</link>
            <g:price>{p['price']:.2f} {p['currency']}</g:price>
            <g:availability>{p['availability']}</g:availability>
        </item>""")

    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
        <channel>
            <title>Mock Google Merchant Center Catalog</title>
            <link>{settings.BASE_URL}</link>
            <description>Simulated GMC Product Catalog Feed for UCP Agents</description>
            {''.join(xml_items)}
        </channel>
    </rss>"""
    return Response(content=xml_content, media_type="application/xml")

# 1. XML Feed Ingestion Endpoint
@app.post("/mock-gmc/upload-xml", summary="Upload and Index Google Merchant Center XML Feed")
async def upload_gmc_xml_feed(file: UploadFile = File(...)):
    """Uploads a standard Google Merchant Center RSS 2.0 XML file and indexes it into DuckDB."""
    if not file.filename.endswith(('.xml', '.rss')):
        raise HTTPException(status_code=400, detail="Only XML/RSS files are supported")
    
    content = await file.read()
    try:
        count = gmc_index.ingest_gmc_xml(content)
        total = len(gmc_index.query_catalog("", limit=1000))
        return {
            "status": "success",
            "message": f"Successfully parsed and indexed {count} items from XML.",
            "total_catalog_size": total
        }
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse XML feed: {str(e)}")

# 2. DuckDB Inspection Endpoint (Verify Tables via SQL)
@app.get("/mock-gmc/inspect", summary="Debug Inspection for DuckDB Tables")
async def inspect_duckdb(query: str = Query("SELECT * FROM gmc_products", description="SQL query to execute")):
    """Allows running SQL queries against the local DuckDB instance to verify tables and schema."""
    try:
        results = gmc_index.run_debug_query(query)
        return {
            "query": query,
            "row_count": len(results),
            "rows": results
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SQL Execution Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)