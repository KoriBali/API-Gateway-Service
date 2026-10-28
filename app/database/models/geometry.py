"""Kolom geometri yang dikirim ke Calculation Service.

Nama dan satuan kolom mengikuti kontrak POST /api/pole/calculate, sehingga
penyusun payload cukup menyalin nilai dengan nama yang sama. Elevasi diukur
dari dasar tiang (0).

Bukan tabel. Mixin di-copy ke tiap subclass, sama seperti FoundationColumnsMixin.
Constraint dibuat lewat fungsi, karena satu objek constraint hanya boleh
menempel ke satu tabel.
"""
import enum
from decimal import Decimal

from sqlalchemy import CheckConstraint, Enum, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


# ===== Enums =====
class PoleType(str, enum.Enum):
    """Bentuk satu segmen. Terpisah dari PoleFamily: tiang taper bisa punya segmen straight."""
    taper = "taper"
    straight = "straight"


class ObjectKind(str, enum.Enum):
    omni = "omni"
    directional = "directional"


# ===== Segmen tiang =====
class PoleSegmentColumnsMixin:
    """Dipakai step_poles, drawing_step_poles, dan pole_standard_segments."""
    name: Mapped[str] = mapped_column(String, nullable=False)
    pole_type: Mapped[PoleType] = mapped_column(Enum(PoleType), nullable=False)
    top_elevation_m: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    diameter_lower_mm: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    diameter_upper_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 5), nullable=True)
    thickness_lower_mm: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    thickness_upper_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 5), nullable=True)


def pole_segment_constraints(table_name: str, parent_column: str) -> tuple:
    return (
        # Straight: kolom upper kosong. Taper: keduanya terisi.
        CheckConstraint(
            "(pole_type = 'straight' AND diameter_upper_mm IS NULL AND thickness_upper_mm IS NULL)"
            " OR (pole_type = 'taper' AND diameter_upper_mm IS NOT NULL AND thickness_upper_mm IS NOT NULL)",
            name="pole_type_dimensions",
        ),
        # Calculation Service menolak nama kembar dan mengurutkan segmen menurut Top Elevation.
        UniqueConstraint(parent_column, "name", name=f"uq_{table_name}_name"),
        UniqueConstraint(parent_column, "top_elevation_m", name=f"uq_{table_name}_top_elevation_m"),
    )


# ===== Objek langsung =====
class DirectObjectColumnsMixin:
    """Dipakai direct_objects dan pole_standard_direct_objects."""
    name: Mapped[str] = mapped_column(String, nullable=False)
    object_kind: Mapped[ObjectKind] = mapped_column(Enum(ObjectKind), nullable=False)
    front_area_m2: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    side_area_m2: Mapped[Decimal | None] = mapped_column(Numeric(10, 5), nullable=True)
    fixed_angle_deg: Mapped[Decimal | None] = mapped_column(Numeric(10, 5), nullable=True)
    mass_per_unit_kg: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    elevation_m: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    base_wind_coefficient: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


def direct_object_constraints(table_name: str, parent_column: str) -> tuple:
    return (
        # Omni: tanpa arah hadap. Directional: keduanya terisi.
        CheckConstraint(
            "(object_kind = 'omni' AND side_area_m2 IS NULL AND fixed_angle_deg IS NULL)"
            " OR (object_kind = 'directional' AND side_area_m2 IS NOT NULL AND fixed_angle_deg IS NOT NULL)",
            name="object_kind_dimensions",
        ),
        UniqueConstraint(parent_column, "name", name=f"uq_{table_name}_name"),
    )