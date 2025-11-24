# Models will be defined here
from sqlalchemy import Column, Integer, String, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from app.database import Base


class WebSocketLog(Base):
    """Model for storing all websocket messages for replay functionality"""
    __tablename__ = "websocket_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tender_id = Column(String, nullable=False, index=True)
    message_data = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Add explicit index on tender_id for fast lookups
    __table_args__ = (
        Index('ix_websocket_logs_tender_id', 'tender_id'),
    )


class Wishlist(Base):
    """Model for storing wishlist/waitlist entries"""
    __tablename__ = "wishlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True, index=True)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

