import asyncio
import json
import uuid
from httpx_sse import connect_sse
import httpx

async def test_streaming():
    # Generate a unique task ID and session ID
    task_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    
    # Create the request payload
    payload = {
        "jsonrpc": "2.0",
        "id": "test_streaming",
        "method": "tasks/sendSubscribe",  # Use the streaming method
        "params": {
            "id": task_id,
            "sessionId": session_id,
            "acceptedOutputModes": ["text"],
            "message": {
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": "Cho tôi thông tin về gói Sức mạnh EKIP"
                    }
                ]
            }
        }
    }
    
    print(f"Sending streaming request with task_id: {task_id}")
    
    # Connect to the SSE stream
    with httpx.Client(timeout=None) as client:
        with connect_sse(client, "POST", "http://localhost:10007/", json=payload) as event_source:
            print("Connected to SSE stream")
            for sse in event_source.iter_sse():
                print(f"Received SSE event: {sse.data}")
                # Parse the JSON data
                try:
                    data = json.loads(sse.data)
                    # Check if this is the final event
                    if "final" in data and data["final"]:
                        print("Received final event, closing connection")
                        break
                except json.JSONDecodeError:
                    print(f"Error decoding JSON: {sse.data}")

if __name__ == "__main__":
    asyncio.run(test_streaming())
