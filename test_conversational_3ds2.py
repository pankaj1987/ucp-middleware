import httpx
import asyncio

BASE_URL = "http://127.0.0.1:8000"

async def test_conversational_3ds2():
    async with httpx.AsyncClient(timeout=30.0) as client:
        session_id = "session-nlp-3ds2-test"
        
        print("\n▶ Step 1: Placing high-value order (> $100)...")
        r1 = await client.post(f"{BASE_URL}/api/v1/agent/chat", json={
            "session_id": session_id,
            "mode": "deterministic",
            "prompt": "Search catalog for Rainbow Glitter High Heels, create a cart for 3 items, checkout with shipping to 100 Market St, San Francisco, CA 94105, and complete the order."
        })
        d1 = r1.json()
        chk = d1["state_snapshot"]["checkout"]
        print(f"Status: {chk['status']} (Amount: ${chk['total_price']})")
        assert chk["status"] == "requires_action", "Expected requires_action"

        print("\n▶ Step 2: Sending natural language OTP in prompt...")
        r2 = await client.post(f"{BASE_URL}/api/v1/agent/chat", json={
            "session_id": session_id,
            "mode": "deterministic",
            "prompt": "My OTP for the transaction is 123456, complete my order."
        })
        d2 = r2.json()
        print(f"Agent Reply:\n{d2['reply']}")
        order = d2["state_snapshot"]["order"]
        assert order is not None, "Order should be confirmed"
        print(f"Confirmed Order: {order.get('order_number') or order.get('order_id')}")
        print("\n✅ In-chat conversational 3DS2 resolution verified successfully!")

if __name__ == "__main__":
    asyncio.run(test_conversational_3ds2())