import asyncio
import json
import os

import websockets

# Adjust these values as needed
BUSINESS_ID = 1  # Replace with a valid business ID in your database
WEBSOCKET_HOST = os.getenv("WEBSOCKET_HOST", "localhost")
WEBSOCKET_PORT = os.getenv("WEBSOCKET_PORT", "8000")

WS_URL = f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}/food/dashboard/ws/{BUSINESS_ID}"

async def test_dashboard_ai():
    async with websockets.connect(WS_URL) as websocket:
        # Send a ping first to ensure connection is alive (optional)
        await websocket.send(json.dumps({"type": "ping"}))
        pong = await websocket.recv()
        print("Received:", pong)

        # Send an AI chat message
        ai_message = {
            "type": "ai_chat",
            "message": "Hello, can you give me a summary of today’s orders?",
            "session_id": "test_session_123",
            "timestamp": "2025-09-16T16:00:00Z"
        }
        await websocket.send(json.dumps(ai_message))
        response = await websocket.recv()
        print("AI Response:", response)

if __name__ == "__main__":
    asyncio.run(test_dashboard_ai())
