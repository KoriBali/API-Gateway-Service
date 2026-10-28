import uuid
import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Numeric,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.database.models.identity import User
    from app.database.models.intake import Request

    from app.database.models.calculation_object import(
        DirectObject,
    )

    from app.database.models.calculation_object import(
        StepPole,
        OverheadWire,
        CalculationBasePlate,
        CalculationOpening,
        CalculationFoundation,
        Arm
    )

    from app.database.models.master import(
        PoleStandard,
        PoleStandardHeight,
        PoleCombination,
        RegionCode,
        DepartmentCode,
        AuthorCode
    )


# ===== Enums =====
class PoleFamily(str, enum.Enum):
    taper = "taper"
    straight = "straight"


class GroundPosition(str, enum.Enum):
    embedment = "embedment"
    on_gl = "on_gl"
    upper_gl = "upper_gl"
    under_gl = "under_gl"
    

class PoleKind(str, enum.Enum):
    standard = "standard"
    custom = "custom"


class StatusCalculationRun(str, enum.Enum):
    ok = "ok"
    ng = "ng"
    failed = "failed"


class CalculationRunType(str, enum.Enum):
    pole = "pole"



# ===== Calculation Case =====
class CalculationCase(Base):
    __tablename__ = "calculation_cases"
    __table_args__ = (
        # Untuk Foreign Key Composit
        UniqueConstraint("id", "request_id", name="uq_calculation_cases_id_request_id"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    created_by_user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('users.id', ondelete="RESTRICT", onupdate="CASCADE")
    )
    
    owner_user_id: Mapped[str] = mapped_column(
            String,
            ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    request_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('requests.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    pole_standard_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('pole_standards.id', ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True
    )

    pole_standard_height_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('pole_standard_heights.id', ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True
    )

    pole_combination_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('pole_combinations.id', ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True
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

    overdesign_factor: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )
    
    evaluated_positions_m: Mapped[list[Decimal] | None] = mapped_column(
        ARRAY(Numeric(10, 5)),
        nullable=True
    )


    title: Mapped[str] = mapped_column(
        String,
        nullable=False
    )
    
    case_label: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )
    
    pole_kind: Mapped[PoleKind] = mapped_column(
        Enum(PoleKind),
        nullable=False
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

    # Parent
    calculation_runs: Mapped[list["CalculationRun"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    direct_objects: Mapped[list["DirectObject"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    step_poles: Mapped[list["StepPole"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    arms: Mapped[list["Arm"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    overhead_wires: Mapped[list["OverheadWire"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    calculation_base_plates: Mapped[list["CalculationBasePlate"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    calculation_openings: Mapped[list["CalculationOpening"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    calculation_foundations: Mapped[list["CalculationFoundation"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    reports: Mapped[list["Report"]] = relationship(
        back_populates="calculation_case",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    # Child
    request: Mapped["Request"] = relationship(
        back_populates="calculation_cases"
    )

    owner_user: Mapped["User"] = relationship(
        back_populates="calculation_cases",
        foreign_keys=[owner_user_id],
    )

    created_by_user: Mapped["User"] = relationship(
        foreign_keys=[created_by_user_id],
    )

    pole_standard: Mapped["PoleStandard | None"] = relationship(
        back_populates="calculation_cases"
    )

    pole_standard_height: Mapped["PoleStandardHeight | None"] = relationship(
        back_populates="calculation_cases"
    )

    pole_combination: Mapped["PoleCombination | None"] = relationship(
        back_populates="calculation_cases"
    )


# ===== Calculation Condition =====
class CalculationCondition(Base):
    """Actual Calculation Condition, satu per request yang memuat calculation. tidak berbarengan dengan intake request"""
    __tablename__ = "calculation_conditions"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    request_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('requests.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        unique=True
    )

    design_standard_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('design_standards.id', ondelete="RESTRICT", onupdate="CASCADE")
    )

    wind_speed: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 5),
        nullable=True
    )

    air_density: Mapped[Decimal] = mapped_column(
        Numeric(10, 5),
        nullable=False
    )

    # Child
    request: Mapped["Request"] = relationship(
        back_populates="calculation_conditions"
    )



# ===== Calculation Run =====
class CalculationRun(Base):
    __tablename__ = "calculation_runs"
    __table_args__ = (
        # Penopang FK komposit parent_run_id: run induk harus milik case yang sama.
        UniqueConstraint("id", "calculation_case_id", name="uq_calculation_runs_id_calculation_case_id"),
        ForeignKeyConstraint(
            ["parent_run_id", "calculation_case_id"],
            ["calculation_runs.id", "calculation_runs.calculation_case_id"],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        CheckConstraint(
            "run_type <> 'pole' OR parent_run_id IS NULL",
            name="run_type_parent",
        ),
        # failed tepat bila hasil kosong dan rincian penolakan terisi.
        CheckConstraint(
            "(status = 'failed') = (result_snapshot IS NULL)"
            " AND (status = 'failed') = (error_snapshot IS NOT NULL)",
            name="status_snapshot",
        ),
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

    run_type: Mapped[CalculationRunType] = mapped_column(
        Enum(CalculationRunType),
        nullable=False
    )

    parent_run_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    status: Mapped[StatusCalculationRun] = mapped_column(
        Enum(StatusCalculationRun),
        nullable=False
    )

    # Body persis yang dikirim ke engine + konteks penyusunnya. Disusun server, tidak pernah dari frontend.
    input_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )

    # none_as_null: Python None disimpan sebagai SQL NULL, bukan JSON 'null',
    # supaya CHECK status_snapshot bisa membedakan kosong dan terisi.
    result_snapshot: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True
    )

    error_snapshot: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True
    )

    run_by_user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('users.id', ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False
    )

    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Child
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="calculation_runs"
    )



# ===== Reports =====
class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    calculation_case_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('calculation_cases.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    region_code_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('region_codes.id', ondelete="CASCADE", onupdate="CASCADE")
    )

    department_code_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('department_codes.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True
    )

    author_code_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey('author_codes.id', ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True
    )

    report_number: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    design_request_management_no: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    report_title_1: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    report_title_2: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    report_title_3: Mapped[str | None] = mapped_column(
        String,
        nullable=True
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
    calculation_case: Mapped["CalculationCase"] = relationship(
        back_populates="reports"
    )

    region_code: Mapped["RegionCode"] = relationship(
        back_populates="reports"
    )

    department_code: Mapped["DepartmentCode"] = relationship(
        back_populates="reports"
    )

    author_code: Mapped["AuthorCode"] = relationship(
        back_populates="reports"
    )