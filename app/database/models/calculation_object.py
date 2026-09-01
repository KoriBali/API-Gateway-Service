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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.database.models.calculation import (
        CalculationCase,
        CalculationResult
    )

    from app.database.models.master import(
        ObjectType
    )



# === Step Pole ===
class StepPole(Base):
    __tablename__ = "step_poles"

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

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    order: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    diameter: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    thickness: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    height: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Parent
    pole_results: Mapped[list["PoleResult"]] = relationship(
        back_populates="step_pole"
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="step_poles"
    )



# === Pole Result ===
class PoleResult(Base):
    __tablename__ = "pole_results"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    step_pole_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('step_poles.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    calculation_result_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_results.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    windload: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    moment: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    # Child
    step_pole: Mapped["StepPole"] = relationship(
        back_populates="pole_results"
    )

    calculation_result: Mapped["CalculationResult"] = relationship(
        back_populates="pole_results"
    )




# === Direct Object ===
class DirectObject(Base):
    __tablename__ = "direct_objects"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    object_type_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('object_types.id', ondelete="RESTRICT", onupdate="CASCADE")
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    front_area: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    height: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    nnc: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    weight: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="direct_objects"
    )

    object_type: Mapped["ObjectType"] = relationship(
        back_populates="direct_objects"
    )

    # Parent
    direct_object_results: Mapped[list["DirectObjectResult"]] = relationship(
        back_populates="direct_object",
        passive_deletes=True
    )



# === Direct Object Result ===
class DirectObjectResult(Base):
    __tablename__ = "direct_object_results"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    direct_object_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('direct_objects.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    calculation_result_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_results.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    windload: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    moment: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    # Child
    direct_object: Mapped["DirectObject"] = relationship(
        back_populates="direct_object_results"
    )

    calculation_result: Mapped["CalculationResult"] = relationship(
        back_populates="direct_object_results"
    )



# === Overhead Wires ===
class OverheadWire(Base):
    __tablename__ = "overhead_wires"

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

    weight: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    diameter: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    fix_height: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    span: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    sagging_ration: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    nnc: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    fix_angle: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    vertical_angle: Mapped[Decimal] = mapped_column(
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
    r = "r"

# === Opening Part ===
class OpeningPart(Base):
    __tablename__ = "opening_parts"

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

    opening_suerface_height: Mapped[Decimal] = mapped_column(
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
        back_populates="opening_parts"
    )



# === Base Plates Type ===
class BasePlateType(str, enum.Enum):
    four_rib = "four_rib"
    eight_rib = "eight_rib"

# === Base Plate ===
class BasePlate(Base):
    __tablename__ = "base_plates"

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

    achor_bolt_diameter: Mapped[Decimal] = mapped_column(
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
        back_populates="base_plates"
    )



# === Foundation Type ===
class FoundationType(str, enum.Enum):
    square = "square"
    circle = "circle"

# === Foundation ===
class Foundation(Base):
    __tablename__ = "foundations"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    type: Mapped[FoundationType] = mapped_column(
        Enum(FoundationType),
        nullable=False
    )

    embedment_depth: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    n_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    gamma_c: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    gamma: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    alpha: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    foundation_width_x: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    foundation_width_y: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    foundation_width: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="foundations"
    )



# === Arm ===
class Arm(Base):
    __tablename__ = "arms"

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

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    diameter: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    thickness: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    length: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    exp_length: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    height: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    distance: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    nnc: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    fix_angle: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    quantity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="arms"
    )

    # Parent
    arm_objects: Mapped[list["ArmObject"]] = relationship(
        back_populates="arm",
        cascade="all, delete-orphan",
        passive_deletes=True
    )



# === Arm Object ===
class ArmObject(Base):
    __tablename__ = "arm_objects"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    arm_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('arms.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    object_type_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('object_types.id', ondelete="RESTRICT", onupdate="CASCADE")
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    front_area: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    weight: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    distance: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    nnc: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Child
    arm: Mapped["Arm"] = relationship(
        back_populates="arm_objects"
    )

    object_type: Mapped["ObjectType"] = relationship(
        back_populates="arm_objects"
    )
