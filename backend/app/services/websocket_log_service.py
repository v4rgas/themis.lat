"""
Service for managing websocket log storage and retrieval
"""
from typing import List, Dict, Any
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import WebSocketLog

logger = logging.getLogger(__name__)


def save_websocket_message(tender_id: str, message: dict) -> None:
    """
    Save a websocket message to the database.
    
    Args:
        tender_id: The tender ID associated with this message
        message: The complete message dictionary to store
    """
    try:
        db: Session = SessionLocal()
        try:
            log_entry = WebSocketLog(
                tender_id=tender_id,
                message_data=message,
                created_at=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving websocket message: {e}", exc_info=True)
            raise
        finally:
            db.close()
    except Exception as e:
        # Log but don't break the websocket flow
        logger.error(f"Failed to save websocket message for tender {tender_id}: {e}", exc_info=True)


def get_websocket_messages(tender_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all websocket messages for a given tender_id, ordered by creation time.
    
    Args:
        tender_id: The tender ID to retrieve messages for
        
    Returns:
        List of message dictionaries, ordered by created_at timestamp
    """
    db: Session = SessionLocal()
    try:
        logs = db.query(WebSocketLog).filter(
            WebSocketLog.tender_id == tender_id
        ).order_by(WebSocketLog.created_at.asc()).all()
        
        # Convert to list of dictionaries
        messages = []
        for log in logs:
            # Convert the message_data JSONB to dict
            message = dict(log.message_data)
            # Include the original timestamp from the database
            message['_db_timestamp'] = log.created_at.isoformat()
            messages.append(message)
        
        return messages
    except Exception as e:
        logger.error(f"Error retrieving websocket messages for tender {tender_id}: {e}", exc_info=True)
        return []
    finally:
        db.close()


def has_websocket_messages(tender_id: str) -> bool:
    """
    Check if any websocket messages exist for a given tender_id.
    
    Args:
        tender_id: The tender ID to check
        
    Returns:
        True if messages exist, False otherwise
    """
    db: Session = SessionLocal()
    try:
        count = db.query(WebSocketLog).filter(
            WebSocketLog.tender_id == tender_id
        ).count()
        return count > 0
    except Exception as e:
        logger.error(f"Error checking websocket messages for tender {tender_id}: {e}", exc_info=True)
        return False
    finally:
        db.close()

