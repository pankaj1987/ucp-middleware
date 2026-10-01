from typing import Dict, Any, List
from adapters.factory import get_commerce_adapter
from core.models.schemas import CartItem, ShippingAddress, AttributionContext
from mock_gmc.engine import gmc_index

adapter = get_commerce_adapter()

async def execute_ucp_tool(name: str, args: Dict[str, Any], session_state: Dict[str, Any]) -> Dict[str, Any]:
    if name == "search_merchant_center_catalog":
        query = args.get("query", "")
        results = gmc_index.query_catalog(query)
        if not results:
            prods = await adapter.search_products(query)
            gmc_index.sync_catalog(prods)
            results = gmc_index.query_catalog(query)
        return {"items": results}

    elif name == "create_shopping_cart":
        item = CartItem(
            product_id=args["product_id"],
            variant_id=args.get("variant_id") or args["product_id"],
            title=args.get("title", "Product"),
            price=float(args.get("price", 0.0)),
            quantity=int(args.get("quantity", 1))
        )
        cart = await adapter.create_cart([item])
        session_state["cart"] = cart.model_dump()
        session_state["items"] = [item]
        return cart.model_dump()

    elif name == "initiate_checkout":
        raw_addr = args.get("shipping_address", {})
        raw_addr.setdefault("first_name", "Valued")
        raw_addr.setdefault("last_name", "Customer")
        raw_addr.setdefault("country", "US")
        session_state["address"] = raw_addr

        addr = ShippingAddress(**raw_addr)
        session = await adapter.init_checkout(
            cart_id=args["cart_id"],
            address=addr,
            items=session_state.get("items", [])
        )
        session_state["checkout"] = session.model_dump()
        return session.model_dump()

    elif name == "finalize_payment_and_order":
        checkout_id = args["checkout_id"]
        token = args.get("payment_token", "AP2_MANDATE_AUTH_OK")
        order_res = await adapter.complete_order(
            checkout_id=checkout_id,
            payment_token=token,
            items=[i.model_dump() if hasattr(i, "model_dump") else i for i in session_state.get("items", [])],
            address=session_state.get("address", {}),
            attribution=AttributionContext()
        )
        session_state["order"] = order_res
        return order_res

    return {"error": f"Unknown tool: {name}"}