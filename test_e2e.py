import asyncio
import httpx
import uuid

async def run_test():
    session_id = f"test-session-{uuid.uuid4().hex[:6]}"
    url = "http://127.0.0.1:8000/api/v1/agent/chat"
    
    prompt = (
        "Find a linen blazer in the catalog, create a cart for 1 unit, "
        "checkout to 555 Market St, San Francisco, CA 94105, and finalize the order."
    )
    
    print(f"\n▶ Sending prompt with thread_id: {session_id}")
    print(f"Prompt: {prompt}\n")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json={"session_id": session_id, "prompt": prompt})
        
        if resp.status_code != 200:
            print("Failed:", resp.text)
            return

        data = resp.json()
        print("=== Tools Executed by LangGraph ===")
        for event in data["tool_history"]:
            print(f"• Tool: {event['tool']}")
            print(f"  Result: {event['result'][:120]}...\n")
            
        print("=== Final Agent Response ===")
        print(data["response"])

if __name__ == "__main__":
    asyncio.run(run_test())