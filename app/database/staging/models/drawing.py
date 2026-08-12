import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Enum, ForeignKey, Date, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from app.core.staging_database import Base

# === Status Case ===
class StatusDrawingCase(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    superseded = "superseded"

# === Drawing Case ===
class DrawingCase(Base):
    __tablename__ = "drawing_cases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String, ForeignKey('requests.id', ondelete="CASCADE", onupdate="CASCADE"))
    owner_user_id = Column(String, ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE"))
    supersedes_case_id = Column(String, ForeignKey('drawing_cases.id', ondelete="CASCADE", onupdate="CASCADE"))
    lighting_companion_id = Column(String, ForeignKey('lighting_company_codes.id', ondelete="CASCADE", onupdate="CASCADE"))
    status = Column(Enum(StatusDrawingCase), default=StatusDrawingCase.draft)
    title = Column(String, nullable=False)
    drawing_type = Column(String, nullable=False)
    drawing_number = Column(String, nullable=False)
    part_number = Column(String, nullable=False)
    designer_name = Column(String, nullable=False)
    checked_by_name = Column(String, nullable=False)
    approved_by_name = Column(String, nullable=False)
    coupling = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
            DateTime, 
            default=lambda: datetime.now(timezone.utc), 
            onupdate=lambda: datetime.now(timezone.utc) 
        )