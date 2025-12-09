"""
Agent workflow API endpoints
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
import asyncio
import time
import logging
from datetime import datetime
import httpx

from app.workflow import FraudDetectionWorkflow
from app.utils.websocket_manager import manager
from app.services.websocket_log_service import get_websocket_messages, has_websocket_messages
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


async def send_investigation_discord_notification(tender_id: str, session_id: str, is_replay: bool = False):
    """
    Send a Discord notification when someone starts an investigation.

    Args:
        tender_id: The tender ID being investigated
        session_id: The session ID for tracking
        is_replay: Whether this is a replay of a previous investigation
    """
    if not settings.discord_webhook_url:
        logger.info("Discord webhook not configured, skipping notification")
        return

    try:
        # Build the Mercado Público link
        mercado_url = f"https://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={tender_id}"

        embed = {
            "title": "🔍 New Investigation Started" if not is_replay else "🔄 Investigation Replay",
            "color": 0x00D166 if not is_replay else 0x5865F2,  # Green for new, blurple for replay
            "fields": [
                {
                    "name": "Tender ID",
                    "value": f"[{tender_id}]({mercado_url})",
                    "inline": True
                },
                {
                    "name": "Session ID",
                    "value": f"`{session_id[:8]}...`",
                    "inline": True
                },
                {
                    "name": "Type",
                    "value": "Replay" if is_replay else "New Analysis",
                    "inline": True
                }
            ],
            "timestamp": datetime.utcnow().isoformat()
        }

        payload = {
            "embeds": [embed]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.discord_webhook_url,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Discord notification sent for investigation {tender_id}")

    except Exception as e:
        # Don't fail the request if Discord notification fails
        logger.error(f"Failed to send Discord notification: {str(e)}")


class InvestigationRequest(BaseModel):
    """Request body for starting an investigation"""
    tender_id: str = Field(
        ...,
        description="Tender ID to investigate",
        example="1234-56-LR22"
    )
    session_id: Optional[str] = Field(
        None,
        description="Optional session ID for WebSocket notifications. If not provided, one will be generated."
    )
    openrouter_api_key: str = Field(
        ...,
        description="OpenRouter API key for LLM calls"
    )


class InvestigationResponse(BaseModel):
    """Response from starting an investigation"""
    session_id: str = Field(..., description="Session ID for tracking this investigation via WebSocket")
    message: str = Field(..., description="Status message")


def replay_websocket_messages(session_id: str, tender_id: str, replay_speed: float):
    """
    Replay saved websocket messages for a tender_id, simulating the original execution.
    
    This function reads all saved messages from the database and sends them through
    the websocket with timing scaled by replay_speed.

    Args:
        session_id: The session ID for WebSocket communication
        tender_id: The tender ID to replay messages for
        replay_speed: Speed multiplier (e.g., 4.0 means 4x faster)
    """
    try:
        # Register tender_id for this session in replay mode (so messages aren't saved again during replay)
        manager.register_tender_id(session_id, tender_id, is_replay=True)
        
        # Get all messages for this tender_id
        messages = get_websocket_messages(tender_id)
        
        if not messages:
            logger.warning(f"No messages found for tender {tender_id}")
            asyncio.run(manager.send_observation(session_id, {
                "type": "error",
                "message": "No saved messages found for replay",
                "status": "error"
            }))
            return
        
        logger.info(f"Replaying {len(messages)} messages for tender {tender_id} at {replay_speed}x speed")
        
        # Send first message immediately
        first_message = messages[0]
        # Remove the _db_timestamp we added
        first_message_clean = {k: v for k, v in first_message.items() if k != '_db_timestamp'}
        asyncio.run(manager.send_observation(session_id, first_message_clean))
        
        # Process remaining messages with timing
        for i in range(1, len(messages)):
            current_msg = messages[i]
            previous_msg = messages[i - 1]
            
            # Get timestamps
            current_timestamp = current_msg.get('_db_timestamp') or current_msg.get('timestamp')
            previous_timestamp = previous_msg.get('_db_timestamp') or previous_msg.get('timestamp')
            
            # Calculate sleep duration
            if current_timestamp and previous_timestamp:
                try:
                    current_dt = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))
                    previous_dt = datetime.fromisoformat(previous_timestamp.replace('Z', '+00:00'))
                    time_diff = (current_dt - previous_dt).total_seconds()
                    sleep_duration = max(0, time_diff / replay_speed)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing timestamps, using default delay: {e}")
                    sleep_duration = 0.1 / replay_speed  # Default 100ms scaled
            else:
                # Fallback: use a small default delay
                sleep_duration = 0.1 / replay_speed
            
            # Sleep to simulate timing
            if sleep_duration > 0:
                time.sleep(sleep_duration)
            
            # Send message (remove _db_timestamp)
            message_clean = {k: v for k, v in current_msg.items() if k != '_db_timestamp'}
            asyncio.run(manager.send_observation(session_id, message_clean))
        
        logger.info(f"Replay completed for tender {tender_id}")
        
    except Exception as e:
        logger.error(f"Error replaying messages for tender {tender_id}: {e}", exc_info=True)
        asyncio.run(manager.send_observation(session_id, {
            "type": "error",
            "message": f"Replay failed: {str(e)}",
            "status": "error"
        }))


def run_workflow_sync(session_id: str, tender_id: str, openrouter_api_key: str):
    """
    Run the fraud detection workflow synchronously.

    This function is called in a background task to run the workflow
    while sending real-time logs via WebSocket.

    Args:
        session_id: The session ID for WebSocket communication
        tender_id: The tender ID to investigate
        openrouter_api_key: OpenRouter API key for LLM calls
    """
    try:
        # Register tender_id for message logging
        manager.register_tender_id(session_id, tender_id)

        # Create workflow instance with user's API key
        workflow = FraudDetectionWorkflow(openrouter_api_key=openrouter_api_key)

        # Run workflow with session_id for streaming
        result = workflow.run(tender_id=tender_id, session_id=session_id)

        # Send final result via WebSocket
        asyncio.run(manager.send_observation(session_id, {
            "type": "result",
            "message": "Investigation completed",
            "tasks_by_id": [
                {
                    "task_id": task.task_id,
                    "task_code": task.task_code,
                    "task_name": task.task_name,
                    "validation_passed": task.validation_passed,
                    "findings_count": len(task.findings),
                    "investigation_summary": task.investigation_summary
                }
                for task in result["tasks_by_id"]
            ],
            "workflow_summary": result["workflow_summary"],
            "status": "completed"
        }))

    except Exception as e:
        logger.error(f"Error in investigation {session_id}: {e}", exc_info=True)

        # Send error to client
        asyncio.run(manager.send_observation(session_id, {
            "type": "error",
            "message": f"Investigation failed: {str(e)}",
            "status": "error"
        }))


@router.post("/investigate", response_model=InvestigationResponse)
async def start_investigation(
    request: InvestigationRequest,
    background_tasks: BackgroundTasks
):
    """
    Start an asynchronous fraud detection investigation workflow.

    The investigation runs in the background and sends real-time log updates
    via WebSocket to the session_id channel.

    Args:
        request: Investigation request containing the tender_id and optional session_id

    Returns:
        InvestigationResponse with the session_id to connect to via WebSocket

    Example:
        POST /api/investigate
        {
            "tender_id": "1234-56-LR22",
            "session_id": "optional-session-id"
        }

        Response:
        {
            "session_id": "abc-123-def",
            "message": "Investigation started. Connect to WebSocket at /ws/abc-123-def"
        }

        Then connect WebSocket:
        ws://localhost:8000/api/ws/abc-123-def
    """
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())

    # Check if messages exist for this tender_id
    if has_websocket_messages(request.tender_id):
        # Replay existing messages instead of running workflow
        logger.info(f"Found existing messages for tender {request.tender_id}, starting replay")

        # Send Discord notification for replay
        await send_investigation_discord_notification(request.tender_id, session_id, is_replay=True)

        background_tasks.add_task(
            replay_websocket_messages,
            session_id,
            request.tender_id,
            settings.websocket_replay_speed
        )
        return InvestigationResponse(
            session_id=session_id,
            message=f"Replay started. Connect to WebSocket at /ws/{session_id} for real-time updates."
        )
    else:
        # No existing messages, run workflow normally (which will save messages)
        logger.info(f"No existing messages for tender {request.tender_id}, starting new workflow")

        # Send Discord notification for new investigation
        await send_investigation_discord_notification(request.tender_id, session_id, is_replay=False)

        background_tasks.add_task(
            run_workflow_sync,
            session_id,
            request.tender_id,
            request.openrouter_api_key
        )
        return InvestigationResponse(
            session_id=session_id,
            message=f"Investigation started. Connect to WebSocket at /ws/{session_id} for real-time updates."
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for the agent API"""
    return {"status": "ok", "service": "agent-api"}
