"""
Agent workflow API endpoints
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
import asyncio
import logging

from app.workflow import FraudDetectionWorkflow
from app.utils.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()


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


class InvestigationResponse(BaseModel):
    """Response from starting an investigation"""
    session_id: str = Field(..., description="Session ID for tracking this investigation via WebSocket")
    message: str = Field(..., description="Status message")


def run_workflow_sync(session_id: str, tender_id: str):
    """
    Run the fraud detection workflow synchronously.

    This function is called in a background task to run the workflow
    while sending real-time logs via WebSocket.

    Args:
        session_id: The session ID for WebSocket communication
        tender_id: The tender ID to investigate
    """
    try:
        # Create workflow instance
        workflow = FraudDetectionWorkflow()

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

    # Start investigation workflow in background
    background_tasks.add_task(run_workflow_sync, session_id, request.tender_id)

    return InvestigationResponse(
        session_id=session_id,
        message=f"Investigation started. Connect to WebSocket at /ws/{session_id} for real-time updates."
    )


@router.get("/health")
async def health_check():
    """Health check endpoint for the agent API"""
    return {"status": "ok", "service": "agent-api"}
