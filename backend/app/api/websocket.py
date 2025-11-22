"""
WebSocket API endpoints for real-time agent observations
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.utils.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for receiving real-time agent observations.

    Clients connect with a session_id and receive observations for that session.
    Multiple clients can connect to the same session.

    Args:
        websocket: The WebSocket connection
        session_id: Unique identifier for the agent workflow session

    Example usage from frontend:
        const ws = new WebSocket('ws://localhost:8000/api/ws/my-session-id');
        ws.onmessage = (event) => {
            const observation = JSON.parse(event.data);
            console.log('Received observation:', observation);
        };
    """
    await manager.connect(websocket, session_id)

    try:
        # Keep connection alive and handle incoming messages if needed
        while True:
            # Wait for any messages from client (e.g., ping/pong, acknowledgments)
            data = await websocket.receive_text()

            # Echo back for debugging (optional)
            logger.debug(f"Received from client in session {session_id}: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
        logger.info(f"Client disconnected from session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error in session {session_id}: {e}")
        manager.disconnect(websocket, session_id)
