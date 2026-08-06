import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Enum, ForeignKey, Date, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.staging_database import Base

# === Status Case ===
class StatusCase(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    superseded = "superseded"

# === Drawing Case ===
class DrawingCase(Base):
    __tablename__ = "drawing_cases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    request_id = Column(String, ForeignKey('requests.id', ondelete="CASCADE", onupdate="CASCADE"))
    owner_user_id = Column(String, ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE"))
    supersedes_case_id = Column(String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    stauts = Column(StatusCase, default=StatusCase.draft)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
            DateTime, 
            default=lambda: datetime.now(timezone.utc), 
            onupdate=lambda: datetime.now(timezone.utc) 
        )