import uuid
import enum
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Enum,
    ForeignKey,
    String,
    Numeric,
    Integer,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.database.models.geometry import (
    ArmColumnsMixin,
    ArmObjectColumnsMixin,
    DirectObjectColumnsMixin,
    PoleSegmentColumnsMixin,
    arm_constraints,
    arm_object_constraints,
    direct_object_constraints,
    pole_segment_constraints,
)

if TYPE_CHECKING:
    from app.database.models.calculation import CalculationCase



# === Step Pole ===
class StepPole(Base, PoleSegmentColumnsMixin):
    __tablename__ = "step_poles"
    __table_args__ = pole_segment_constraints("step_poles", "calculation_case_id")

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True, default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    material_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('materials.id', ondelete="RESTRICT", onupdate="CASCADE")
    )

    # Tidak dikirim ke engine. Aplikasi menolak nilai selain 1.
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="step_poles"
    )



# === Direct Object ===
class DirectObject(Base, DirectObjectColumnsMixin):
    __tablename__ = "direct_objects"
    __table_args__ = direct_object_constraints("direct_objects", "calculation_case_id")

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="direct_objects"
    )


# === Overhead Wires ===
class OverheadWire(Base):
    """Isian user, tanpa katalog. Nama dan satuan kolom mengikuti kontrak Calculation Service."""
    __tablename__ = "overhead_wires"
    __table_args__ = (
        UniqueConstraint("calculation_case_id", "name", name="uq_overhead_wires_name"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    mass_per_length_kg_m: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    diameter_mm: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    elevation_m: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    span_length_m: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    # Persen, misalnya 3.
    sag_ratio_percent: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    base_wind_coefficient: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    fixed_angle_deg: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    vertical_angle_deg: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="overhead_wires"
    )


# === Opening Type ===
class OpeningType(str, enum.Enum):
    box = "box"
    rounded = "rounded"

# === Opening Direction (only drawing) ===
class OpeningDirection(str, enum.Enum):
    left = "left"
    right = "right"
    front = "front"
    back = "back"

# === Calculation Opening ===
class CalculationOpening(Base):
    __tablename__ = "calculation_openings"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    type: Mapped[OpeningType] = mapped_column(
        Enum(OpeningType),
        nullable=False
    )

    opening_width: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    box_width: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    opening_surface_height: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    box_thickness: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    opening_length: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="calculation_openings"
    )



# === Base Plates Type ===
class BasePlateType(str, enum.Enum):
    four_rib = "four_rib"
    eight_rib = "eight_rib"

# === Base Plate ===
class CalculationBasePlate(Base):
    __tablename__ = "calculation_base_plates"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    type: Mapped[BasePlateType] = mapped_column(
        Enum(BasePlateType),
        nullable=False
    )

    base_plate_width: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    anchor_pitch: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    anchor_bolt_diameter: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    base_plate_thickness: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    rib_plate_height: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    rib_plate_length: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    rib_plate_thickness: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    rib_plate_scallop: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    rib_plate_angle: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    weld_leg_length: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="calculation_base_plates"
    )



# === Foundation Type ===
class FoundationType(str, enum.Enum):
    square = "square"
    circle = "circle"

# === Mixin for calculation & drawing ===
class FoundationColumnsMixin:
    """Definisi kolom dipakai bersama oleh CalculationFoundation & DrawingFoundation.
    Bukan tabel — hanya declarative mixin. Kolom di-copy ke tiap subclass."""
    type: Mapped[FoundationType] = mapped_column(Enum(FoundationType), nullable=False)
    embedment_depth: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    n_value: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    gamma_c: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    gamma: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    alpha: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    foundation_width: Mapped[Decimal | None] = mapped_column(Numeric(10, 5), nullable=True)    
    foundation_width_x: Mapped[Decimal | None] = mapped_column(Numeric(10, 5), nullable=True)  
    foundation_width_y: Mapped[Decimal | None] = mapped_column(Numeric(10, 5), nullable=True)  



# === Calculation Foundation ===
class CalculationFoundation(Base, FoundationColumnsMixin):
    __tablename__ = "calculation_foundations"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    calculation_case_id: Mapped[str] = mapped_column(
        String, ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="calculation_foundations"
    )



# === Arm ===
class Arm(Base, ArmColumnsMixin):
    __tablename__ = "arms"
    __table_args__ = arm_constraints("arms", "calculation_case_id")

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    material_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('materials.id', ondelete="RESTRICT", onupdate="CASCADE")
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="arms"
    )

    # Parent
    arm_objects: Mapped[list["ArmObject"]] = relationship(
        back_populates="arm",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ArmObject.name",
    )



# === Arm Object ===
class ArmObject(Base, ArmObjectColumnsMixin):
    __tablename__ = "arm_objects"
    __table_args__ = arm_object_constraints("arm_objects", "arm_id")

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    arm_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('arms.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    # Child
    arm: Mapped["Arm"] = relationship(
        back_populates="arm_objects"
    )