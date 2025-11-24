"""
Wishlist API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging

from app.database import get_db
from app.models import Wishlist
from app.schemas import WishlistCreate, WishlistResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/wishlist", response_model=WishlistResponse, status_code=201)
def create_wishlist_entry(
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
