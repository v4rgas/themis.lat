"""
WebSocket connection manager for real-time agent observations
"""
from typing import Dict, Set
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasts messages to connected clients.

    Supports multiple sessions, where each session can have multiple connected clients.
    """

    def __init__(self):
        # Maps session_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """
        Accept a WebSocket connection and add it to the session.

        Args:
            websocket: The WebSocket connection to add
            session_id: The session ID to associate with this connection
        """
        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()

        self.active_connections[session_id].add(websocket)
        logger.info(f"Client connected to session {session_id}. Total connections: {len(self.active_connections[session_id])}")

    def disconnect(self, websocket: WebSocket, session_id: str):
        """
        Remove a WebSocket connection from the session.

        Args:
            websocket: The WebSocket connection to remove
            session_id: The session ID to remove the connection from
        """
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)

            # Clean up empty sessions
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

            logger.info(f"Client disconnected from session {session_id}")

    async def send_observation(self, session_id: str, observation: dict):
        """
        Send an observation to all clients connected to a session.

        Args:
            session_id: The session ID to send the observation to
            observation: The observation data to send (will be JSON serialized)
        """
        if session_id not in self.active_connections:
            logger.warning(f"No active connections for session {session_id}")
            return

        # Create a copy of the set to avoid modification during iteration
        connections = self.active_connections[session_id].copy()

        # Send to all connected clients
        disconnected = []
        for connection in connections:
            try:
                await connection.send_json(observation)
            except Exception as e:
                logger.error(f"Error sending to client in session {session_id}: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection, session_id)

    async def send_text(self, session_id: str, message: str):
        """
        Send a text message to all clients connected to a session.

        Args:
            session_id: The session ID to send the message to
            message: The text message to send
        """
        if session_id not in self.active_connections:
            logger.warning(f"No active connections for session {session_id}")
            return

        connections = self.active_connections[session_id].copy()

        disconnected = []
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending to client in session {session_id}: {e}")
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection, session_id)


# Global connection manager instance
manager = ConnectionManager()
