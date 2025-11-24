"""
Wishlist API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging
import httpx
from typing import List

from app.database import get_db
from app.models import Wishlist
from app.schemas import WishlistCreate, WishlistResponse
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


async def send_discord_notification(email: str, reason: str):
    """
    Send a Discord notification when a new wishlist entry is created.

    Args:
        email: User's email address
        reason: User's reason for joining
    """
    if not settings.discord_webhook_url:
        logger.info("Discord webhook not configured, skipping notification")
        return

    try:
        embed = {
            "title": "🆕 New Wishlist Entry",
            "color": 0x5865F2,  # Discord blurple
            "fields": [
                {
                    "name": "Email",
                    "value": email,
                    "inline": False
                },
                {
                    "name": "Reason",
                    "value": reason,
                    "inline": False
                }
            ]
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
            logger.info(f"Discord notification sent for {email}")

    except Exception as e:
        # Don't fail the request if Discord notification fails
        logger.error(f"Failed to send Discord notification: {str(e)}")


@router.post("/wishlist", response_model=WishlistResponse, status_code=201)
async def create_wishlist_entry(
    wishlist_data: WishlistCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new wishlist entry.

    Args:
        wishlist_data: The wishlist data containing email and reason
        db: Database session

    Returns:
        WishlistResponse with the created entry

    Raises:
        HTTPException: If email already exists or database error occurs
    """
    try:
        # Create new wishlist entry
        db_wishlist = Wishlist(
            email=wishlist_data.email,
            reason=wishlist_data.reason
        )

        db.add(db_wishlist)
        db.commit()
        db.refresh(db_wishlist)

        logger.info(f"Wishlist entry created for email: {wishlist_data.email}")

        # Send Discord notification (don't await to avoid blocking the response)
        await send_discord_notification(wishlist_data.email, wishlist_data.reason)

        return db_wishlist

    except IntegrityError:
        db.rollback()
        logger.warning(f"Duplicate wishlist entry attempted for email: {wishlist_data.email}")
        raise HTTPException(
            status_code=409,
            detail="Este correo electrónico ya está registrado en la lista de espera"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating wishlist entry: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error al procesar tu solicitud"
        )


@router.get("/wishlist", response_model=List[WishlistResponse])
def list_wishlist_entries(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    """
    List all wishlist entries. Protected by API key.

    Args:
        x_api_key: API key in X-API-Key header
        db: Database session

    Returns:
        List of all wishlist entries ordered by creation date

    Raises:
        HTTPException: If API key is invalid or database error occurs
    """
    # Verify API key
    if x_api_key != settings.admin_api_key:
        logger.warning("Invalid API key attempt to access wishlist")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    try:
        # Fetch all wishlist entries ordered by creation date (newest first)
        wishlist_entries = db.query(Wishlist).order_by(Wishlist.created_at.desc()).all()
        logger.info(f"Retrieved {len(wishlist_entries)} wishlist entries")
        return wishlist_entries

    except Exception as e:
        logger.error(f"Error retrieving wishlist entries: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error al obtener los datos"
        )
