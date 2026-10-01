import re
import time
import logging
from typing import Dict, Any, List
from agents.gemini_agent import gemini_agent, AgentResponse, ToolActionRecord
from core.tools_schema import execute_ucp_tool

logger = logging.getLogger("ucp.router")

class GoogleUCPRouter:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "cart": None,
                "checkout": None,
                "order": None,
                "items": [],
                "address": {}
            }
        return self.sessions[session_id]

    async def resolve_action_challenge(self, session_id: str, challenge_id: str, otp_code: str) -> Dict[str, Any]:
        """
        Validates dynamically generated 3DS2 OTP against challenge state with
        expiration window check and attempt limits.
        """
        state = self.get_session_state(session_id)
        checkout = state.get("checkout")
        if not checkout or checkout.get("status") != "requires_action":
            raise ValueError("No active pending 3DS2 challenge found in session.")

        challenge = checkout.get("action_challenge", {})
        expected_otp = challenge.get("_expected_otp")
        expires_at = challenge.get("expires_at", 0)

        # 1. Expiration validation
        if expires_at and time.time() > expires_at:
            checkout["status"] = "failed"
            raise ValueError("3DS2 passcode has expired. Please initiate checkout again.")

        # 2. OTP matching validation
        if not expected_otp or str(otp_code).strip() != str(expected_otp).strip():
            attempts = challenge.get("attempts_remaining", 1) - 1
            challenge["attempts_remaining"] = attempts
            if attempts <= 0:
                checkout["status"] = "failed"
                raise ValueError("Maximum authentication attempts exceeded. Transaction declined.")
            raise ValueError(f"Invalid verification code. {attempts} attempt(s) remaining.")

        logger.info(f"Verified dynamic 3DS2 challenge '{challenge_id}' successfully.")

        # Complete order with authenticated token
        ord_res = await execute_ucp_tool(
            "finalize_payment_and_order",
            {
                "checkout_id": checkout["checkout_id"],
                "payment_token": f"3DS2_DYNAMIC_AUTH_VERIFIED_{otp_code}"
            },
            state
        )
        checkout["status"] = "completed"
        return ord_res

    async def _execute_deterministic(self, prompt: str, state: Dict[str, Any], notice: str = "") -> AgentResponse:
        logger.info("Executing Deterministic Fallback Engine (0 tokens, no external LLM calls)")
        actions: List[ToolActionRecord] = []

        # 1. Intent Extraction: Extract product name keyword
        search_term = "Rainbow Glitter High Heels"
        for candidate in ["rainbow glitter high heels", "high heels", "hoodie", "blazer", "pants", "chino"]:
            if candidate in prompt.lower():
                search_term = candidate
                break

        search_res = await execute_ucp_tool("search_merchant_center_catalog", {"query": search_term}, state)
        actions.append(ToolActionRecord(
            tool="search_merchant_center_catalog",
            input={"query": search_term},
            output=search_res
        ))

        items = search_res.get("items", [])
        if not items:
            return AgentResponse(
                agent_name="deterministic",
                reply=f"{notice}Item not found in catalog.",
                actions=actions,
                state_snapshot=state
            )

        target = items[0]

        # Extract purchase quantity from prompt (e.g., '3 items' or '3 heels' triggers > $100 rule)
        qty_match = re.search(r"\b(\d+)\s*(items?|pieces?|units?|heels?|pairs?)?\b", prompt.lower())
        qty = int(qty_match.group(1)) if qty_match and int(qty_match.group(1)) > 0 else 1
        if "three" in prompt.lower():
            qty = 3

        # 2. Assemble Cart
        cart_args = {
            "product_id": target["id"],
            "variant_id": target.get("variant_id") or target["id"],
            "title": target["title"],
            "price": float(target["price"]),
            "quantity": qty
        }
        cart_res = await execute_ucp_tool("create_shopping_cart", cart_args, state)
        actions.append(ToolActionRecord(
            tool="create_shopping_cart",
            input=cart_args,
            output=cart_res
        ))

        # 3. Initiate Checkout
        addr_match = re.search(r"(\d+\s+[^,]+),\s*([^,]+),\s*([A-Z]{2})\s*(\d{5})", prompt)
        address = {
            "first_name": "Valued",
            "last_name": "Customer",
            "address_line1": addr_match.group(1) if addr_match else "100 Market St",
            "city": addr_match.group(2) if addr_match else "San Francisco",
            "postal_code": addr_match.group(4) if addr_match else "94105",
            "country": "US"
        }
        chk_args = {"cart_id": cart_res["cart_id"], "shipping_address": address}
        chk_res = await execute_ucp_tool("initiate_checkout", chk_args, state)
        actions.append(ToolActionRecord(
            tool="initiate_checkout",
            input=chk_args,
            output=chk_res
        ))

        # Check if 3DS2 Step-up Challenge is required
        if chk_res.get("status") == "requires_action":
            reply = (
                f"Total order value is ${chk_res['total_price']:.2f}. "
                f"Elevated risk check triggered: a dynamic 3DS2 one-time passcode has been generated. "
                f"Please provide your 6-digit verification code to complete payment."
            )
            return AgentResponse(
                agent_name="deterministic",
                reply=reply,
                actions=actions,
                state_snapshot=state
            )

        # 4. Finalize Payment & Order (if below $100 risk threshold)
        ord_args = {"checkout_id": chk_res["checkout_id"], "payment_token": "AP2_MANDATE_AUTH_OK"}
        ord_res = await execute_ucp_tool("finalize_payment_and_order", ord_args, state)
        actions.append(ToolActionRecord(
            tool="finalize_payment_and_order",
            input=ord_args,
            output=ord_res
        ))

        order_ref = ord_res.get("order_number") or ord_res.get("order_id") or "1001"
        reply = (
            f"{notice}Order #{order_ref} placed successfully for {target['title']} (x{qty}). "
            f"Total: ${chk_res.get('total_price', target['price']):.2f} USD."
        )
        return AgentResponse(
            agent_name="deterministic",
            reply=reply,
            actions=actions,
            state_snapshot=state
        )

    async def route(self, mode: str, prompt: str, session_id: str) -> AgentResponse:
        state = self.get_session_state(session_id)
        mode_normalized = mode.lower().strip()

        # --- Natural Language In-Chat 3DS2 Resolution Interceptor ---
        checkout = state.get("checkout")
        if checkout and checkout.get("status") == "requires_action":
            # Extract any 6-digit code provided in conversational prompt
            otp_match = re.search(r"\b(\d{6})\b", prompt)
            if otp_match:
                otp_code = otp_match.group(1)
                challenge_id = checkout.get("action_challenge", {}).get("challenge_id", "3ds_challenge")
                logger.info(f"Detected conversational OTP '{otp_code}' for challenge '{challenge_id}'")
                try:
                    ord_res = await self.resolve_action_challenge(
                        session_id=session_id,
                        challenge_id=challenge_id,
                        otp_code=otp_code
                    )
                    order_ref = ord_res.get("order_number") or ord_res.get("order_id") or "Confirmed"
                    reply = (
                        f"✔ 3DS2 Step-Up Verification Successful! Your order has been placed. "
                        f"Shopify Order: {order_ref}. Total: ${ord_res.get('total_price', '')} {ord_res.get('currency', 'USD')}."
                    )
                    actions = [
                        ToolActionRecord(
                            tool="resolve_3ds2_challenge",
                            input={"challenge_id": challenge_id, "otp_code": otp_code},
                            output=ord_res
                        )
                    ]
                    return AgentResponse(
                        agent_name="3ds2_security_gateway",
                        reply=reply,
                        actions=actions,
                        state_snapshot=state
                    )
                except Exception as e:
                    return AgentResponse(
                        agent_name="3ds2_security_gateway",
                        reply=f"❌ Verification Error: {str(e)}",
                        actions=[],
                        state_snapshot=state
                    )
            else:
                return AgentResponse(
                    agent_name="3ds2_security_gateway",
                    reply="Your checkout is currently paused awaiting 3DS2 authentication. Please provide the 6-digit verification code (e.g. 'My OTP is 739204') to proceed.",
                    actions=[],
                    state_snapshot=state
                )
        # -------------------------------------------------------------

        if mode_normalized in ("deterministic", "rules", "test", "0-token"):
            return await self._execute_deterministic(prompt, state)

        try:
            return await gemini_agent.chat(prompt, session_id, state)
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "quota" in err_msg or "resource_exhausted" in err_msg:
                notice = "[Google API Free Tier 20/day Quota Hit (429) - Automatically executed via Offline Engine]\n\n"
                return await self._execute_deterministic(prompt, state, notice=notice)
            raise e

router = GoogleUCPRouter()