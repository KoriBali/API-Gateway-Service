import uuid
import enum
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.database.models.calculation import CalculationCase
    from app.database.models.drawing import DrawingCase



# ===== Enums =====
class Role(str, enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    drafter = "drafter"


class RequestStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    superseded = "superseded"


class RequestType(str, enum.Enum):
    generally = "generally"
    special = "special"


class DesignType(str, enum.Enum):
    drawing = "drawing"
    calculation = "calculation"
    drawing_calculation = "drawing_calculation"


class RequestCategory(str, enum.Enum):
    new = "new"
    revision = "revision"
    modification = "modification"
    replacement = "replacement"


class PoleKind(str, enum.Enum):
    standard = "standard"
    custom = "custom"



# ===== Department =====
class Department(Base):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    code: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True
    )

    # Parent
    users: Mapped[list["User"]] = relationship(
        back_populates="department",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    requests: Mapped[list["Request"]] = relationship(
        back_populates="responsible_department",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )




# ===== User =====
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    department_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "departments.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=True,
    )

    role: Mapped[Role] = mapped_column(
        Enum(Role),
        default=Role.drafter,
        nullable=False,
    )

    username: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Child
    department: Mapped["Department"] = relationship(
        back_populates="users",
    )

    # Parent
    requests: Mapped[list["Request"]] = relationship(
        back_populates="created_by_user",
        passive_deletes=True,
    )

    calculation_cases: Mapped[list["CalculationCase"]] = relationship(
        back_populates="owner_user",
        passive_deletes=True,
    )

    drawing_cases: Mapped[list["DrawingCase"]] = relationship(
        back_populates="owner_user",
        passive_deletes=True,
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True
    )



# ===== Refresh Token =====
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )

    token_hash: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Child
    user: Mapped["User"] = relationship(
        back_populates="refresh_tokens",
    )



# ===== Request =====
class Request(Base):
    __tablename__ = "requests"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    responsible_department_id: Mapped[str] = mapped_column(
        ForeignKey(
            "departments.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )

    created_by_user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )

    pole_category_id: Mapped[str] = mapped_column(
        ForeignKey(
            "pole_categories.id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )

    supersedes_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("requests.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )

    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus),
        default=RequestStatus.draft,
        server_default=RequestStatus.draft.value,
        nullable=False,
    )

    request_no: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    receipt_no: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    pj_no: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    request_type: Mapped[RequestType] = mapped_column(
        Enum(RequestType),
        nullable=False,
    )

    design_type: Mapped[DesignType] = mapped_column(
        Enum(DesignType),
        nullable=False,
    )

    request_category: Mapped[RequestCategory] = mapped_column(
        Enum(RequestCategory),
        nullable=False,
    )

    pole_kind: Mapped[PoleKind | None] = mapped_column(
        Enum(PoleKind),
        nullable=True,
    )

    company_name: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    project_name: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Self
    supersedes: Mapped["Request | None"] = relationship(
        "Request",
        remote_side=[id],
        back_populates="superseded_by",
    )
    superseded_by: Mapped[list["Request"]] = relationship(
        back_populates="supersedes",
    )

    # Child
    created_by_user: Mapped["User"] = relationship(
        back_populates="requests",
    )

    responsible_department: Mapped["Department"] = relationship(
        back_populates="requests",
    )

    # Parent
    calculation_cases: Mapped[list["CalculationCase"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    drawing_cases: Mapped[list["DrawingCase"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
