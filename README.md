mkdir ucp-middleware\config && mkdir ucp-middleware\core\models && mkdir ucp-middleware\mock_gmc && mkdir ucp-middleware\adapters\shopify && mkdir ucp-middleware\agents\tools && mkdir ucp-middleware\api


for /r "ucp-middleware" %d in (.) do @type nul > "%d\__init__.py"


1:python -m venv .venv
2:.venv\Scripts\activate
pip install -r requirements.txt

#To create DB schema
psql -U postgres -c "CREATE DATABASE ucp_commerce;"

#Deactivate virtual env
deactivate
rmdir /s /q .venv 

Start the Middleware:
uvicorn main:app --reload --host 127.0.0.1 --port 8000

Verify Local GMC Feed:
curl http://127.0.0.1:8000/mock-gmc/products


Execute End-to-End Flow:
In another terminal, run:
python test_e2e.py


Verify PostgreSQL Persistence:
Query your local PostgreSQL database:
SELECT thread_id, checkpoint_id, parent_checkpoint_id FROM checkpoints;

#Verify the XML Feed
http://127.0.0.1:8000/mock-gmc/feed.xml

#Test 2: Ingest a New Custom Product via API
You can index custom items dynamically without restarting the server:
curl -X POST http://127.0.0.1:8000/mock-gmc/index-products \
  -H "Content-Type: application/json" \
  -d '[
    {
      "id": "gid://shopify/Product/9999",
      "title": "Smart Noise Cancelling Headphones",
      "description": "Wireless over-ear headphones with active noise cancellation and 40h battery.",
      "price": 299.00,
      "currency": "USD",
      "sku": "AUDIO-NC-99",
      "in_stock": true,
      "vertical_type": "shopping"
    }
  ]'

  #
  curl http://127.0.0.1:8000/mock-gmc/products


  @app.post("/mock-gmc/sync", summary="Re-index Catalog from Commerce Adapter")
  Full Wipe & Replace (DELETE FROM + insert). Syncing the index with live products from Shopify or Hybris.
  :@app.post("/mock-gmc/index-products", summary="Manually Push Products to GMC Index") 
  Upsert / Additive (INSERT OR REPLACE). Programmatic scripting, test automation (pytest), or quick ad-hoc additions.
  /mock-gmc/upload-xml
  Upsert / Additive (INSERT OR REPLACE). Testing real merchant feed files, legacy ERP feed dumps, or external Google Merchant Center exports.



Gemini tets file
python test_gemini_native.py


Swagger URL:
http://localhost:8000/docs#/default/upload_gmc_xml_feed_mock_gmc_upload_xml_post


#REact UI setup
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install lucide-react

#To start front end
cd frontend
npm run dev
  