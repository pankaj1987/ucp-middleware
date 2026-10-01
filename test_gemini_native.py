import asyncio
import httpx

async def test_native():
    url = "http://127.0.0.1:8000/api/v1/agent/native-gemini"
    prompt = (
        "Search the merchant center catalog for Rainbow Glitter High Heels, "
        "add 1 item to cart, set shipping to 100 Market Street, San Francisco, CA 94105, "
        "and complete the order directly."
    )
    
    print(f"\n▶ Sending prompt to Native Gemini Agent:\n{prompt}\n")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json={"prompt": prompt})
        
        if resp.status_code != 200:
            print("Error:", resp.text)
            return
            
        data = resp.json()
        print("=== Executed UCP Tool Actions ===")
        for act in data.get("actions", []):
            print(f"✔ Action: {act['tool']}")
            print(f"  Output: {act['output']}\n")
            
        print("=== Gemini Reply ===")
        print(data.get("assistant_reply"))

if __name__ == "__main__":
    asyncio.run(test_native())