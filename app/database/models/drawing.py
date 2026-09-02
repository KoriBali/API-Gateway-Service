import uuid
import enum
from decimal import Decimal
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Boolean,
    Numeric,
    Integer
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

from app.database.models.calculation_object import (
    OpeningType, OpeningDirection, BasePlateType,
    FoundationColumnsMixin,
)

from app.database.models.calculation import PoleFamily, GroundPosition

if TYPE_CHECKING:
    from app.database.models.identity import(
        User,
        Request,
    )

    from app.database.models.master import(
        LightingCompanyCode,
        PoleStandard,
        PoleStandardHeight
    )



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

    lighting_company_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('lighting_company_codes.id', ondelete="RESTRICT", onupdate="CASCADE")
    )

    pole_standard_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('pole_standards.id', ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    pole_standard_height_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('pole_standard_heights.id', ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
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

    pole_family: Mapped[PoleFamily | None] = mapped_column(
        Enum(PoleFamily), 
        nullable=True
    )

    ground_position: Mapped[GroundPosition | None] = mapped_column(
        Enum(GroundPosition), 
        nullable=True
    )

    lowest_height: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5), 
        nullable=True
    )

    embedment_length: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5), 
        nullable=True
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

    # Parent
    drawing_openings: Mapped[list["DrawingOpening"]] = relationship(
        back_populates="drawing_case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    drawing_base_plates: Mapped[list["DrawingBasePlate"]] = relationship(
        back_populates="drawing_case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    drawing_foundations: Mapped[list["DrawingFoundation"]] = relationship(
        back_populates="drawing_case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    drawing_step_poles: Mapped[list["DrawingStepPole"]] = relationship(
        back_populates="drawing_case",
        cascade="all, delete-orphan",
        passive_deletes=True,
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



# === Drawing Opening ===
class DrawingOpening(Base):
    __tablename__ = "drawing_openings"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    drawing_case_id: Mapped[str] = mapped_column(
        String, ForeignKey('drawing_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )
    type: Mapped[OpeningType] = mapped_column(Enum(OpeningType), nullable=False)
    opening_direction: Mapped[OpeningDirection] = mapped_column(
        Enum(OpeningDirection), nullable=False
    )
    opening_length: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)

    drawing_case: Mapped["DrawingCase"] = relationship(back_populates="drawing_openings")


# === Drawing Base Plate ===
class DrawingBasePlate(Base):
    __tablename__ = "drawing_base_plates"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    drawing_case_id: Mapped[str] = mapped_column(
        String, ForeignKey('drawing_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )
    type: Mapped[BasePlateType] = mapped_column(Enum(BasePlateType), nullable=False)
    base_plate_width: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)

    drawing_case: Mapped["DrawingCase"] = relationship(back_populates="drawing_base_plates")


# === Drawing Foundation ===
class DrawingFoundation(Base, FoundationColumnsMixin):
    __tablename__ = "drawing_foundations"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    drawing_case_id: Mapped[str] = mapped_column(
        String, ForeignKey('drawing_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )
    drawing_case: Mapped["DrawingCase"] = relationship(back_populates="drawing_foundations")



# === Drawing Step Pole ===
class DrawingStepPole(Base):
    __tablename__ = "drawing_step_poles"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    drawing_case_id: Mapped[str] = mapped_column(
        String, ForeignKey('drawing_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )
    material_id: Mapped[str] = mapped_column(
        String, ForeignKey('materials.id', ondelete="RESTRICT", onupdate="CASCADE")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    diameter: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    thickness: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    height: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Child
    drawing_case: Mapped["DrawingCase"] = relationship(back_populates="drawing_step_poles")