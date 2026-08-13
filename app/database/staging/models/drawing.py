import uuid
import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.staging_database import Base

if TYPE_CHECKING:
    from app.database.staging.models.identity import(
        User,
        Request,
    )

    from app.database.staging.models.master import(
        LightingCompanyCode
    )


# === Status Case ===
class StatusDrawingCase(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    superseded = "superseded"

# === Drawing Case ===
class DrawingCase(Base):
    __tablename__ = "drawing_cases"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    request_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('requests.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    owner_user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    supersedes_case_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('drawing_cases.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True
    )

    lighting_company_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('lighting_company_codes.id', ondelete="RESTRICT", onupdate="CASCADE")
    )

    status: Mapped[StatusDrawingCase] = mapped_column(
        Enum(StatusDrawingCase),
        default=StatusDrawingCase.draft
    )

    title: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    drawing_type: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    drawing_number: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    part_number: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    designer_name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    checked_by_name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    approved_by_name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    coupling: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Child
    request: Mapped["Request"] = relationship(
        back_populates="drawing_cases"
    )

    owner_user: Mapped["User"] = relationship(
        back_populates="drawing_cases"
    )

    lighting_company: Mapped["LightingCompanyCode"] = relationship(
        back_populates="drawing_cases"
    )
