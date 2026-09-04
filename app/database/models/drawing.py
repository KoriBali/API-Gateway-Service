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
    Integer,
    UniqueConstraint
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

# === Surface Enums ===
class SurfaceTreatmentOption(str, enum.Enum):
    plating_only = "plating_only"
    plating_painting = "plating_painting"


class PlatingType(str, enum.Enum):
    standard = "standard"
    non_standard = "non_standard"


class PaintingType(str, enum.Enum):
    acrylic_silicone = "acrylic_silicone"    
    stain_coating = "stain_coating"
    ceramic_coating = "ceramic_coating"
    specified_color_paint = "specified_color_paint"


# Nilai "Specific Plating Type Code"
PLATING_DEFAULT_SPEC = {
    PlatingType.standard: "HZTD",
}


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

    drawing_coupling_heights: Mapped[list["DrawingCouplingHeight"]] = relationship(
        back_populates="drawing_case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    drawing_surface: Mapped["DrawingSurface | None"] = relationship(
        back_populates="drawing_case",
        uselist=False,
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



# === Drawing Coupling Height ===
class DrawingCouplingHeight(Base):
    __tablename__ = "drawing_coupling_heights"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    drawing_case_id: Mapped[str] = mapped_column(
        String, ForeignKey("drawing_cases.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    height_index: Mapped[int] = mapped_column(Integer, nullable=False)          # slot 1=H1, 2=H2, 3=H3
    height_value: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)  # mm
    has_hookband: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("drawing_case_id", "height_index", name="uq_coupling_height_slot"),
    )

    drawing_case: Mapped["DrawingCase"] = relationship(back_populates="drawing_coupling_heights")
    couplings: Mapped[list["DrawingCoupling"]] = relationship(
        back_populates="height", cascade="all, delete-orphan", passive_deletes=True,
    )


# === Drawing Coupling ===
class DrawingCoupling(Base):
    __tablename__ = "drawing_couplings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    height_id: Mapped[str] = mapped_column(
        String, ForeignKey("drawing_coupling_heights.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    coupling_case_id: Mapped[str] = mapped_column(
        String, ForeignKey("coupling_cases.id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    height: Mapped["DrawingCouplingHeight"] = relationship(back_populates="couplings")
    groups: Mapped[list["DrawingCouplingGroup"]] = relationship(
        back_populates="coupling", cascade="all, delete-orphan", passive_deletes=True,
    )


# === Drawing Coupling Group ===
class DrawingCouplingGroup(Base):
    __tablename__ = "drawing_coupling_groups"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    coupling_id: Mapped[str] = mapped_column(
        String, ForeignKey("drawing_couplings.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    group_index: Mapped[int] = mapped_column(Integer, nullable=False)   # 1=CP1, 2=CP2

    position_id: Mapped[str] = mapped_column(
        String, ForeignKey("coupling_positions.id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    size_id: Mapped[str] = mapped_column(
        String, ForeignKey("coupling_sizes.id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    type_id: Mapped[str] = mapped_column(
        String, ForeignKey("coupling_types.id", ondelete="RESTRICT", onupdate="CASCADE")
    )

    vertical_angle: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)  # derajat, default 0
    distance: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)          # hanya pair_distance
    horizontal_angle: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)  # hanya pair_angular
    custom_name: Mapped[str | None] = mapped_column(String, nullable=True)                       # "Other" (opsional)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("coupling_id", "group_index", name="uq_coupling_group_index"),
    )

    coupling: Mapped["DrawingCoupling"] = relationship(back_populates="groups")
    external_objects: Mapped[list["DrawingCouplingGroupExternalObject"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", passive_deletes=True,
    )


# === Drawing Coupling External Object ===
class DrawingCouplingGroupExternalObject(Base):
    __tablename__ = "drawing_coupling_group_external_objects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id: Mapped[str] = mapped_column(
        String, ForeignKey("drawing_coupling_groups.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    external_object_id: Mapped[str] = mapped_column(
        String, ForeignKey("external_objects.id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("group_id", "external_object_id", name="uq_group_external_object"),
    )

    group: Mapped["DrawingCouplingGroup"] = relationship(back_populates="external_objects")



# === Drawing Surface (1:1 dengan DrawingCase) ===
class DrawingSurface(Base):
    __tablename__ = "drawing_surfaces"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )

    drawing_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("drawing_cases.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )

    treatment_option: Mapped[SurfaceTreatmentOption | None] = mapped_column(
        Enum(SurfaceTreatmentOption), nullable=True
    )

    # Plating
    plating_type: Mapped[PlatingType | None] = mapped_column(
        Enum(PlatingType), nullable=True
    )
    plating_spec: Mapped[str | None] = mapped_column(
        String, nullable=True
    ) 

    # Painting
    painting_type: Mapped[PaintingType | None] = mapped_column(
        Enum(PaintingType), nullable=True
    )

    # Specified Color Details
    color_name: Mapped[str | None] = mapped_column(String, nullable=True)
    munsell_value: Mapped[str | None] = mapped_column(String, nullable=True)
    color_code: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("drawing_case_id", name="uq_drawing_surface_case"), 
    )

    drawing_case: Mapped["DrawingCase"] = relationship(back_populates="drawing_surface")