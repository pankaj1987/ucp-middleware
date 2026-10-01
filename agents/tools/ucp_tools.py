from langchain_core.tools import tool
from adapters.factory import get_commerce_adapter
from mock_gmc.engine import gmc_index
from core.models.schemas import CartItem, ShippingAddress
import json

adapter = get_commerce_adapter()

@tool
async def search_merchant_center_catalog(query: str) -> str:
    """Searches the Google Merchant Center product catalog for items, prices, and stock."""
    results = gmc_index.query_catalog(query)
    if not results:
        # Fall back to live adapter search
        prods = await adapter.search_products(query)
        gmc_index.sync_catalog(prods)
        results = gmc_index.query_catalog(query)
    return json.dumps(results)

@tool
async def create_cart(product_id: str, title: str, price: float, quantity: int = 1) -> str:
    """Creates a UCP cart with selected line items."""
    item = CartItem(product_id=product_id, title=title, price=price, quantity=quantity)
    cart = await adapter.create_cart([item])
    return cart.model_dump_json()

@tool
async def init_checkout(cart_id: str, address_line: str, city: str, postal_code: str, first_name: str = "Valued", last_name: str = "Customer") -> str:
    """Initializes checkout session with a shipping delivery address."""
    addr = ShippingAddress(
        first_name=first_name,
        last_name=last_name,
        address_line1=address_line,
        city=city,
        postal_code=postal_code
    )
    session = await adapter.init_checkout(cart_id, address=addr)
    return session.model_dump_json()

@tool
async def complete_order(checkout_id: str, payment_token: str = "DUMMY_CARD_TOKEN_OK") -> str:
    """Submits authorization and captures payment to create an order."""
    result = await adapter.complete_order(checkout_id, payment_token)
    return json.dumps(result)

COMMERCE_TOOLS = [
    search_merchant_center_catalog,
    create_cart,
    init_checkout,
    complete_order
]