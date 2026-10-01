from typing import Dict, Any, List
from google import genai
from google.genai import types
from pydantic import BaseModel
from config.settings import settings
from core.tools_schema import execute_ucp_tool

class ToolActionRecord(BaseModel):
    tool: str
    input: Dict[str, Any]
    output: Any

class AgentResponse(BaseModel):
    agent_name: str
    reply: str
    actions: List[ToolActionRecord]
    state_snapshot: Dict[str, Any]

class GeminiShoppingAgent:
    """Pure Google Gemini Shopping Agent executing autonomous in-chat UCP workflows."""

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
        self.tools = [
            types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name="search_merchant_center_catalog",
                    description="Search the Google Merchant Center catalog for products, variants, and prices.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={"query": types.Schema(type="STRING", description="Search query or title keyword")},
                        required=["query"]
                    )
                ),
                types.FunctionDeclaration(
                    name="create_shopping_cart",
                    description="Builds an active shopping cart with the product and variant ID.",
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
                    description="Prepares checkout with delivery address.",
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
                    description="Authorizes payment using AP2 token and places the order directly in Shopify.",
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

    async def chat(self, prompt: str, session_id: str, session_state: Dict[str, Any]) -> AgentResponse:
        if not self.client:
            raise ValueError("GEMINI_API_KEY is not configured.")

        system_instruction = (
            "You are an autonomous Google UCP Shopping Assistant operating inside Gemini UI. "
            "Execute the end-to-end shopping journey (search_merchant_center_catalog -> create_shopping_cart -> "
            "initiate_checkout -> finalize_payment_and_order) if given complete instructions. "
            "Confirm the Shopify order number and details directly in chat upon completion."
        )

        chat_session = self.client.chats.create(
            model=settings.GEMINI_MODEL,
            config=types.GenerateContentConfig(
                tools=self.tools,
                temperature=0.0,
                system_instruction=system_instruction
            )
        )

        response = chat_session.send_message(prompt)
        actions: List[ToolActionRecord] = []
        turn = 0

        while response.function_calls and turn < 8:
            turn += 1
            tool_parts = []
            for call in response.function_calls:
                call_args = {k: v for k, v in call.args.items()}
                result = await execute_ucp_tool(call.name, call_args, session_state)
                actions.append(ToolActionRecord(tool=call.name, input=call_args, output=result))
                tool_parts.append(types.Part.from_function_response(name=call.name, response={"result": result}))

            response = chat_session.send_message(tool_parts)

        return AgentResponse(
            agent_name="gemini",
            reply=response.text or "Order completed successfully.",
            actions=actions,
            state_snapshot=session_state
        )

gemini_agent = GeminiShoppingAgent()