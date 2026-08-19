import uuid
import enum
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Enum,
    ForeignKey,
    String,
    Numeric,
    Boolean,
    JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.staging_database import Base

if TYPE_CHECKING:
    from app.database.models.calculation import(
        CalculationCase,
        Report
    )

    from app.database.models.calculation_object import(
        ArmObject,
        DirectObject
    )

    from app.database.models.drawing import(
        DrawingCase
    )


# === Material ===
class Material(Base):
    __tablename__ = 'materials'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )



# === Pole Category ===
class PoleCategory(Base):
    __tablename__ = 'pole_categories'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Parent
    design_standards: Mapped[list["DesignStandard"]] = relationship(
        back_populates="pole_category",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    pole_standards: Mapped[list["PoleStandard"]] = relationship(
        back_populates="pole_category",
        cascade="all, delete-orphan",
        passive_deletes=True
    )



# === Design Standard ===
class DesignStandard(Base):
    __tablename__ = 'design_standards'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    pole_category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('pole_categories.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    default_wind_speed: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    default_air_density: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Child
    pole_category: Mapped["PoleCategory"] = relationship(
        back_populates="design_standards"
    )



# === Pole Standard Type ===
class PoleStandardType(str, enum.Enum):
    taper = "taper"
    straight = "straight"

# === Pole Standard ===
class PoleStandard(Base):
    __tablename__ = 'pole_standards'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    pole_category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('pole_categories.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    type: Mapped[PoleStandardType] = mapped_column(
        Enum(PoleStandardType),
        nullable=False
    )

    geometry: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Child
    pole_category: Mapped["PoleCategory"] = relationship(
        back_populates="pole_standards"
    )

    # Parent
    pole_standard_heights: Mapped[list["PoleStandardHeight"]] = relationship(
        back_populates="pole_standard",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    pole_diameters: Mapped[list["PoleDiameter"]] = relationship(
        back_populates="pole_standard",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    calculation_cases: Mapped[list["CalculationCase"]] = relationship(
        back_populates="pole_standard",
        passive_deletes=True
    )



# === Pole Standard Height ===
class PoleStandardHeight(Base):
    __tablename__ = 'pole_standard_heights'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    pole_standard_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('pole_standards.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False
    )

    height: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Child
    pole_standard: Mapped["PoleStandard"] = relationship(
        back_populates="pole_standard_heights"
    )

    # Parent
    calculation_cases: Mapped[list["CalculationCase"]] = relationship(
        back_populates="pole_standard_height",
        passive_deletes=True
    )



# === Pole Diameter ===
class PoleDiameter(Base):
    __tablename__ = 'pole_diameters'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    pole_standard_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('pole_standards.id', ondelete='CASCADE', onupdate='CASCADE')
    )

    diameter: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Child
    pole_standard: Mapped["PoleStandard"] = relationship(
        back_populates="pole_diameters"
    )

    # Parent
    pole_combinations: Mapped[list["PoleCombination"]] = relationship(
        back_populates="pole_diameter",
        cascade="all, delete-orphan",
        passive_deletes=True
    )



# === Pole Combination ===
class PoleCombination(Base):
    __tablename__ = 'pole_combinations'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    pole_diameter_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('pole_diameters.id', ondelete='CASCADE', onupdate='CASCADE')
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Child
    pole_diameter: Mapped["PoleDiameter"] = relationship(
        back_populates="pole_combinations"
    )

    # Parent
    pole_thicknesses: Mapped[list["PoleThickness"]] = relationship(
        back_populates="pole_combination",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    calculation_cases: Mapped[list["CalculationCase"]] = relationship(
        back_populates="pole_combination",
        passive_deletes=True
    )



# === Pole Thickness Position ===
class PoleThicknessPosition(str, enum.Enum):
    upper = "upper"
    lower = "lower"

# === Pole Thickness ===
class PoleThickness(Base):
    __tablename__ = 'pole_thicknesses'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    pole_combination_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('pole_combinations.id', ondelete='CASCADE', onupdate='CASCADE')

    )

    position: Mapped[PoleThicknessPosition] = mapped_column(
        Enum(PoleThicknessPosition),
        nullable=False
    )

    thickness: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Child
    pole_combination: Mapped["PoleCombination"] = relationship(
        back_populates="pole_thicknesses"
    )



# === Region Code ===
class RegionCode(Base):
    __tablename__ = 'region_codes'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    code: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    label: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Parent
    reports: Mapped[list["Report"]] = relationship(
        back_populates="region_code",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


# === Department Code ===
class DepartmentCode(Base):
    __tablename__ = 'department_codes'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    code: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    label: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Parent
    reports: Mapped[list["Report"]] = relationship(
        back_populates="department_code",
        cascade="all, delete-orphan",
        passive_deletes=True
    )



# === Author Code ===
class AuthorCode(Base):
    __tablename__ = 'author_codes'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    code: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    label: Mapped[str] = mapped_column(
        String,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Parent
    reports: Mapped[list["Report"]] = relationship(
        back_populates="author_code",
        cascade="all, delete-orphan",
        passive_deletes=True
    )



# === Lighting Company Code ===
class LightingCompanyCode(Base):
    __tablename__ = 'lighting_company_codes'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    code: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    label: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Parent
    drawing_cases: Mapped[list["DrawingCase"]] = relationship(
        back_populates="lighting_company",
        passive_deletes=True
    )



# === Object Type ===
class ObjectType(Base):
    __tablename__ = 'object_types'

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Parent
    direct_objects: Mapped[list["DirectObject"]] = relationship(
        back_populates="object_type",
        passive_deletes=True
    )

    arm_objects: Mapped[list["ArmObject"]] = relationship(
        back_populates="object_type",
        passive_deletes=True
    )
