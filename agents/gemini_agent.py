import json
from typing import Dict, Any, List
from google import genai
from google.genai import types

from config.settings import settings
from adapters.factory import get_commerce_adapter
from core.models.schemas import CartItem, ShippingAddress, LocationRef
from mock_gmc.engine import gmc_index

adapter = get_commerce_adapter()

# Global turn state store for multi-step agent context
session_context: Dict[str, Any] = {
    "items": [],
    "address": {}
}

async def execute_tool_call(name: str, args: dict) -> dict:
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
        session_context["items"] = [item.model_dump()]
        cart = await adapter.create_cart([item])
        return cart.model_dump()

    elif name == "initiate_checkout":
        raw_addr = args.get("shipping_address", {})
        raw_addr.setdefault("first_name", "Valued")
        raw_addr.setdefault("last_name", "Customer")
        raw_addr.setdefault("country", "US")
        session_context["address"] = raw_addr
        
        addr = ShippingAddress(**raw_addr)
        session = await adapter.init_checkout(cart_id=args["cart_id"], address=addr)
        return session.model_dump()

    elif name == "finalize_payment_and_order":
        checkout_id = args["checkout_id"]
        token = args.get("payment_token", "AP2_MANDATE_AUTH_OK")
        order_res = await adapter.complete_order(
            checkout_id=checkout_id,
            payment_token=token,
            items=session_context["items"],
            address=session_context["address"]
        )
        return order_res

    return {"error": f"Unknown tool: {name}"}


class GeminiShoppingAgent:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.tools = [
            types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name="search_merchant_center_catalog",
                    description="Search catalog for product details, variant ID, and price.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={"query": types.Schema(type="STRING")},
                        required=["query"]
                    )
                ),
                types.FunctionDeclaration(
                    name="create_shopping_cart",
                    description="Assembles cart using product_id, variant_id, and price.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "product_id": types.Schema(type="STRING"),
                            "variant_id": types.Schema(type="STRING"),
                            "title": types.Schema(type="STRING"),
                            "price": types.Schema(type="NUMBER"),
                            "quantity": types.Schema(type="INTEGER")
                        },
                        required=["product_id", "price"]
                    )
                ),
                types.FunctionDeclaration(
                    name="initiate_checkout",
                    description="Prepares checkout session with shipping details.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "cart_id": types.Schema(type="STRING"),
                            "shipping_address": types.Schema(
                                type="OBJECT",
                                properties={
                                    "first_name": types.Schema(type="STRING"),
                                    "last_name": types.Schema(type="STRING"),
                                    "address_line1": types.Schema(type="STRING"),
                                    "city": types.Schema(type="STRING"),
                                    "postal_code": types.Schema(type="STRING")
                                },
                                required=["address_line1", "city", "postal_code"]
                            )
                        },
                        required=["cart_id"]
                    )
                ),
                types.FunctionDeclaration(
                    name="finalize_payment_and_order",
                    description="Commits the order directly to Shopify using autonomous UCP agent authority.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "checkout_id": types.Schema(type="STRING"),
                            "payment_token": types.Schema(type="STRING")
                        },
                        required=["checkout_id"]
                    )
                )
            ])
        ]

    async def chat(self, user_prompt: str) -> Dict[str, Any]:
        system_instruction = (
            "You are an autonomous Google UCP Shopping Agent operating directly within Gemini UI. "
            "When the user confirms a purchase, complete all four steps end-to-end without redirecting: "
            "1. search_merchant_center_catalog "
            "2. create_shopping_cart "
            "3. initiate_checkout "
            "4. finalize_payment_and_order "
            "Once finalized, report the confirmed Shopify order number and order ID directly in the chat."
        )

        chat = self.client.chats.create(
            model=settings.GEMINI_MODEL,
            config=types.GenerateContentConfig(
                tools=self.tools,
                temperature=0.0,
                system_instruction=system_instruction
            )
        )

        response = chat.send_message(user_prompt)
        executed_actions: List[Dict[str, Any]] = []

        turn = 0
        while response.function_calls and turn < 10:
            turn += 1
            tool_responses = []

            for call in response.function_calls:
                call_args = {k: v for k, v in call.args.items()}
                action_result = await execute_tool_call(call.name, call_args)

                executed_actions.append({
                    "tool": call.name,
                    "input": call_args,
                    "output": action_result
                })

                tool_responses.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={"result": action_result}
                    )
                )

            response = chat.send_message(tool_responses)

        return {
            "assistant_reply": response.text,
            "actions": executed_actions
        }

gemini_agent = GeminiShoppingAgent()