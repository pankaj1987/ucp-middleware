import httpx
import asyncio

BASE_URL = "http://127.0.0.1:8000"

async def test_phase3():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n🧪 --- 1. Testing Policy Snapshot & Permalink Generation ---")
        chat_req = {
            "session_id": "test-p3-session",
            "mode": "deterministic",
            "prompt": "Search catalog for Rainbow Glitter High Heels, create a cart for 1 item, checkout with address 100 Market St, San Francisco, CA 94105, and complete the order."
        }
        res = await client.post(f"{BASE_URL}/api/v1/agent/chat", json=chat_req)
        assert res.status_code == 200, f"Chat failed: {res.text}"
        data = res.json()
        
        cart = data["state_snapshot"]["cart"]
        assert cart["permalink"] is not None, "Permalink missing from cart"
        assert len(cart["policies"]) >= 2, "Policies missing from cart"
        print(f"✔ Cart subtotal: ${cart['subtotal']} {cart['currency']}")
        print(f"✔ Generated Permalink: {cart['permalink']}")
        print(f"✔ Retained Policies: {[p['policy_id'] for p in cart['policies']]}")

        print("\n🧪 --- 2. Testing Permalink Hydration Endpoint (/cart/recover) ---")
        token = cart["permalink"].split("token=")[-1]
        rec_res = await client.get(f"{BASE_URL}/cart/recover", params={"token": token})
        assert rec_res.status_code == 200, f"Recovery failed: {rec_res.text}"
        rec_data = rec_res.json()
        assert rec_data["status"] == "hydrated", "Cart failed to hydrate"
        print(f"✔ Recovered Cart ID: {rec_data['cart']['cart_id']}")

        print("\n🧪 --- 3. Testing 3DS2 Step-Up Challenge (> $100 Rule) ---")
        high_value_req = {
            "session_id": "test-p3-high-value",
            "mode": "deterministic",
            "prompt": "Search catalog for Rainbow Glitter High Heels, create a cart for 3 items, checkout with address 100 Market St, San Francisco, CA 94105, and complete the order."
        }
        hv_res = await client.post(f"{BASE_URL}/api/v1/agent/chat", json=high_value_req)
        assert hv_res.status_code == 200
        hv_data = hv_res.json()
        chk = hv_data["state_snapshot"]["checkout"]
        assert chk["status"] == "requires_action", f"Expected requires_action, got {chk['status']}"
        challenge_id = chk["action_challenge"]["challenge_id"]
        print(f"✔ Step-up Challenge Triggered: {challenge_id} (Total: ${chk['total_price']})")

        print("\n🧪 --- 4. Resolving 3DS2 Step-Up Challenge ---")
        resolve_req = {
            "session_id": "test-p3-high-value",
            "challenge_id": challenge_id,
            "otp_code": "123456"
        }
        res_res = await client.post(f"{BASE_URL}/api/v1/ucp/actions/resolve", json=resolve_req)
        assert res_res.status_code == 200, f"Challenge resolution failed: {res_res.text}"
        res_data = res_res.json()
        assert res_data["status"] == "challenge_resolved"
        order = res_data["order"]
        print(f"✔ Order Confirmed Post-3DS2: {order.get('order_number') or order.get('order_id')}")
        print("\n🎉 ALL PHASE 3 SPEC COMPLIANCE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_phase3())