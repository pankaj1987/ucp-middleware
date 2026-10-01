import duckdb
import xml.etree.ElementTree as ET
import re
from typing import List, Dict, Any
from core.models.schemas import Product

class LocalGMCIndex:
    def __init__(self, db_path: str = ":memory:"):
        # Use ":memory:" for RAM or "gmc_catalog.duckdb" for persistent file storage
        self.conn = duckdb.connect(database=db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS gmc_products (
                id VARCHAR PRIMARY KEY,
                title VARCHAR,
                description VARCHAR,
                price DOUBLE,
                currency VARCHAR,
                availability VARCHAR,
                link VARCHAR
            )
        """)
        self.seed_default_catalog()

    def seed_default_catalog(self):
        default_products = [
            Product(
                id="gid://shopify/Product/1001",
                title="Structured Linen Blazer",
                description="Breathable organic linen blazer tailored for comfort and formal wear.",
                price=185.00,
                currency="USD",
                sku="LINEN-BLZ-01",
                in_stock=True
            ),
            Product(
                id="gid://shopify/Product/1002",
                title="Merino Wool Travel Hoodie",
                description="Moisture-wicking, temperature-regulating travel pullover with zippered pockets.",
                price=120.00,
                currency="USD",
                sku="MERINO-HD-02",
                in_stock=True
            ),
            Product(
                id="gid://shopify/Product/1003",
                title="Performance Chino Pants",
                description="Four-way stretch wrinkle-resistant everyday chinos.",
                price=95.00,
                currency="USD",
                sku="PERF-CHINO-03",
                in_stock=True
            )
        ]
        self.sync_catalog(default_products)

    def insert_products(self, products: List[Product]):
        for p in products:
            self.conn.execute("""
                INSERT OR REPLACE INTO gmc_products VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                p.id,
                p.title,
                p.description,
                p.price,
                p.currency,
                "in stock" if p.in_stock else "out of stock",
                f"http://localhost:8000/products/{p.id}"
            ))

    def sync_catalog(self, products: List[Product]):
        self.conn.execute("DELETE FROM gmc_products")
        for p in products:
            self.conn.execute("""
                INSERT INTO gmc_products VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                p.id,
                p.title,
                p.description,
                p.price,
                p.currency,
                "in stock" if p.in_stock else "out of stock",
                f"http://localhost:8000/products/{p.id}"
            ))

    def ingest_gmc_xml(self, xml_bytes: bytes) -> int:
        """
        Parses standard Google Merchant Center RSS 2.0 XML feeds
        with namespace xmlns:g='http://base.google.com/ns/1.0'
        and loads records directly into DuckDB.
        """
        root = ET.fromstring(xml_bytes)
        ns = {'g': 'http://base.google.com/ns/1.0'}
        
        # Locate all <item> elements under <channel>
        items = root.findall('.//item')
        parsed_products = []

        for item in items:
            # 1. Product ID
            g_id = item.find('g:id', ns)
            item_id = g_id.text.strip() if g_id is not None and g_id.text else (
                item.findtext('id', default='').strip() or f"item_{len(parsed_products) + 1}"
            )

            # 2. Title & Description
            title = (item.findtext('title') or item.findtext('g:title', default='', namespaces=ns)).strip()
            description = (item.findtext('description') or item.findtext('g:description', default='', namespaces=ns)).strip()

            # 3. Price & Currency (e.g., '149.99 USD' or 'USD 149.99')
            price_elem = item.find('g:price', ns)
            price_text = price_elem.text.strip() if price_elem is not None and price_elem.text else (
                item.findtext('price', default='0.0 USD').strip()
            )

            price_match = re.search(r"(\d+(\.\d+)?)", price_text)
            price = float(price_match.group(1)) if price_match else 0.0

            curr_match = re.search(r"([A-Z]{3})", price_text)
            currency = curr_match.group(1) if curr_match else "USD"

            # 4. Availability & Link
            avail_elem = item.find('g:availability', ns)
            availability = avail_elem.text.strip().lower() if avail_elem is not None and avail_elem.text else "in stock"
            link = (item.findtext('link') or item.findtext('g:link', default='', namespaces=ns)).strip()

            self.conn.execute("""
                INSERT OR REPLACE INTO gmc_products VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id,
                title,
                description,
                price,
                currency,
                availability,
                link or f"http://localhost:8000/products/{item_id}"
            ))
            parsed_products.append(item_id)

        return len(parsed_products)

    def query_catalog(self, query: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        if not query or query.strip() == "":
            cursor = self.conn.execute("""
                SELECT id, title, description, price, currency, availability, link
                FROM gmc_products
                LIMIT ?
            """, (limit,))
        else:
            cursor = self.conn.execute("""
                SELECT id, title, description, price, currency, availability, link
                FROM gmc_products
                WHERE lower(title) LIKE lower(?) OR lower(description) LIKE lower(?)
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit))

        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def run_debug_query(self, sql: str) -> List[Dict[str, Any]]:
        """Runs an inspection SQL query against DuckDB."""
        cursor = self.conn.execute(sql)
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

gmc_index = LocalGMCIndex()