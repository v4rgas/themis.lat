"""
WebSocket connection manager for real-time agent observations
"""
from typing import Dict, Set, Optional
from fastapi import WebSocket
import json
import logging

from app.services.websocket_log_service import save_websocket_message

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasts messages to connected clients.

    Supports multiple sessions, where each session can have multiple connected clients.
    """

    def __init__(self):
        # Maps session_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Maps session_id -> tender_id for message logging
        self.session_to_tender_id: Dict[str, str] = {}
        # Set of session_ids that are in replay mode (don't save messages)
        self.replay_sessions: Set[str] = set()

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
    
    def register_tender_id(self, session_id: str, tender_id: str, is_replay: bool = False):
        """
        Register a tender_id for a session to enable message logging.
        
        Args:
            session_id: The session ID
            tender_id: The tender ID associated with this session
            is_replay: If True, mark this session as replay mode (won't save messages)
        """
        self.session_to_tender_id[session_id] = tender_id
        if is_replay:
            self.replay_sessions.add(session_id)
        logger.debug(f"Registered tender_id {tender_id} for session {session_id} (replay={is_replay})")

    async def send_observation(self, session_id: str, observation: dict):
        """
        Send an observation to all clients connected to a session.
        Also saves the message to the database if tender_id is registered for this session.

        Args:
            session_id: The session ID to send the observation to
            observation: The observation data to send (will be JSON serialized)
        """
        # Send to websocket clients first
        if session_id in self.active_connections:
            # Create a copy of the set to avoid modification during iteration
            connections = self.active_connections[session_id].copy()

            # Send to all connected clients
            disconnected = []
            for connection in connections:
                try:
                    await connection.send_json(observation)
                except Exception as e:
                    import traceback
                    logger.error(f"Error sending to client in session {session_id}: {e}")
                    traceback.print_exc()
                    disconnected.append(connection)

            # Clean up disconnected clients
            for connection in disconnected:
                self.disconnect(connection, session_id)
        else:
            logger.warning(f"No active connections for session {session_id}")

        # Save message to database if tender_id is registered for this session and not in replay mode
        tender_id = self.session_to_tender_id.get(session_id)
        if tender_id and session_id not in self.replay_sessions:
            try:
                save_websocket_message(tender_id, observation)
            except Exception as e:
                # Log but don't break the websocket flow
                logger.error(f"Failed to save websocket message for session {session_id}: {e}", exc_info=True)

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
                import traceback
                logger.error(f"Error sending to client in session {session_id}: {e}")
                traceback.print_exc()
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection, session_id)


# Global connection manager instance
manager = ConnectionManager()
