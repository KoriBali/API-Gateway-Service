"""Alur kerja request: peristiwa, putaran revisi, berkas
dan versinya, assignment dan jam kerja, serta NC Prevention Checklist.

Tabel di sini hanya menyimpan data. Aturan turunan (siklus submit, gate submit,
status prevention_check, G4, G6, G9) hidup di lapisan aplikasi.
"""
import uuid
import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
# Tipe bersama `designtype`: revision_rounds.work_scope berbagi tipe dengan requests.design_type.
from app.database.models.intake import DesignType

if TYPE_CHECKING:
    from app.database.models.identity import User



# ===== Enums =====
class WorkType(str, enum.Enum):
    calculation = "calculation"
    drawing = "drawing"


class EventType(str, enum.Enum):
    ready_for_check = "ready_for_check"
    check = "check"
    submit = "submit"
    feedback = "feedback"
    clear = "clear"
    reopen = "reopen"
    cancel = "cancel"
    ownership_transfer = "ownership_transfer"


class CheckResult(str, enum.Enum):
    clean = "clean"
    has_findings = "has_findings"


class RevisionOrigin(str, enum.Enum):
    internal_correction = "internal_correction"
    japan_correction = "japan_correction"


class FileRole(str, enum.Enum):
    deliverable = "deliverable"
    concept_brief = "concept_brief"
    note_attachment = "note_attachment"
    reference = "reference"
    check_result = "check_result"


class RefKind(str, enum.Enum):
    request_cover = "request_cover"
    request_detail = "request_detail"


class DeliverableSubtype(str, enum.Enum):
    calculation_report = "calculation_report"
    calculation_file = "calculation_file"
    schematic_drawing = "schematic_drawing"
    main_sheet = "main_sheet"
    detail_sheet = "detail_sheet"
    bill_of_materials = "bill_of_materials"


class LifecycleStatus(str, enum.Enum):
    active = "active"
    obsolete = "obsolete"


class AssignmentStatus(str, enum.Enum):
    active = "active"
    released = "released"


class ChecklistItemStatus(str, enum.Enum):
    pending = "pending"
    done = "done"
    not_applicable = "not_applicable"



# ===== Request Event =====
class RequestEvent(Base):
    """Append-only. Sengaja TANPA FK keluar: riwayat tetap utuh walau
    request, user, atau case-nya dihapus. Tidak pernah di-UPDATE atau di-DELETE."""
    __tablename__ = "request_events"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    actor_user_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType),
        nullable=False,
    )

    # Terisi untuk ready_for_check, check, ownership_transfer; kosong untuk peristiwa
    # tingkat request. work_type menyebut tabel case yang dirujuk.
    case_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    work_type: Mapped[WorkType | None] = mapped_column(
        Enum(WorkType),
        nullable=True,
    )

    check_result: Mapped[CheckResult | None] = mapped_column(
        Enum(CheckResult),
        nullable=True,
    )

    payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )



# ===== Revision Round =====
class RevisionRound(Base):
    __tablename__ = "revision_rounds"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_id: Mapped[str] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )

    # Satu-satunya FK yang menunjuk request_events. RESTRICT: peristiwa append-only.
    check_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("request_events.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )

    round_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    work_scope: Mapped[DesignType] = mapped_column(
        Enum(DesignType),
        nullable=False,
    )

    origin: Mapped[RevisionOrigin] = mapped_column(
        Enum(RevisionOrigin),
        nullable=False,
    )

    round_label: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    round_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    trigger_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )



# ===== Request File =====
class RequestFile(Base):
    __tablename__ = "request_files"
    __table_args__ = (
        # Deliverable menempel ke paling banyak satu case.
        CheckConstraint(
            "calculation_case_id IS NULL OR drawing_case_id IS NULL",
            name="at_most_one_case",
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_id: Mapped[str] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )

    uploaded_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )

    file_role: Mapped[FileRole] = mapped_column(
        Enum(FileRole),
        nullable=False,
    )

    ref_kind: Mapped[RefKind | None] = mapped_column(
        Enum(RefKind),
        nullable=True,
    )

    # Deliverable adalah bagian dari isi case, jadi ikut terhapus bersama case-nya.
    calculation_case_id: Mapped[str | None] = mapped_column(
        ForeignKey("calculation_cases.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
    )

    drawing_case_id: Mapped[str | None] = mapped_column(
        ForeignKey("drawing_cases.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
    )

    deliverable_subtype: Mapped[DeliverableSubtype | None] = mapped_column(
        Enum(DeliverableSubtype),
        nullable=True,
    )

    request_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("request_events.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )

    file_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    # Path objek di bucket Supabase Storage. Hanya untuk role TIDAK berversi
    # (check_result, note_attachment, reference); role berversi menyimpannya per versi.
    storage_ref: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Parent
    versions: Mapped[list["FileVersion"]] = relationship(
        back_populates="request_file",
        foreign_keys="FileVersion.request_file_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )



# ===== File Version =====
class FileVersion(Base):
    __tablename__ = "file_versions"
    __table_args__ = (
        # Satu berkas paling banyak satu versi aktif.
        Index(
            "uq_file_versions_active_per_file",
            "request_file_id",
            unique=True,
            postgresql_where=text("lifecycle_status = 'active'"),
        ),
        # Tepat satu bentuk versi: file unggahan ATAU penunjuk run.
        CheckConstraint(
            "(storage_ref IS NULL) <> (calculation_run_id IS NULL)",
            name="exactly_one_form",
        ),
        CheckConstraint(
            "(report_header_snapshot IS NULL) = (calculation_run_id IS NULL)",
            name="snapshot_iff_run",
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_file_id: Mapped[str] = mapped_column(
        ForeignKey("request_files.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )

    revision_round_id: Mapped[str | None] = mapped_column(
        ForeignKey("revision_rounds.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )

    version_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus),
        default=LifecycleStatus.active,
        nullable=False,
    )

    previous_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("file_versions.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )

    storage_ref: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    # RESTRICT: run yang sudah diserahkan adalah bukti.
    calculation_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("calculation_runs.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )

    uploaded_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )

    report_header_snapshot: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    render_template_version: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Child
    request_file: Mapped["RequestFile"] = relationship(
        back_populates="versions",
        foreign_keys=[request_file_id],
    )



# ===== Request Assignment =====
class RequestAssignment(Base):
    """Per work type, tidak pernah per case. Terpisah dari kepemilikan case."""
    __tablename__ = "request_assignments"
    __table_args__ = (
        # Satu orang paling banyak satu assignment aktif per work type di satu request.
        Index(
            "uq_request_assignments_active_per_worker",
            "request_id", "assignee_user_id", "work_type",
            unique=True,
            postgresql_where=text("assignment_status = 'active'"),
        ),
        # Kolom pelepasan terisi tepat saat status released.
        CheckConstraint(
            "(assignment_status = 'active' AND released_at IS NULL AND released_by_user_id IS NULL) OR "
            "(assignment_status = 'released' AND released_at IS NOT NULL AND released_by_user_id IS NOT NULL)",
            name="release_fields_match_status",
        ),
    )


    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_id: Mapped[str] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )

    assignee_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )

    assigned_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )

    work_type: Mapped[WorkType] = mapped_column(
        Enum(WorkType),
        nullable=False,
    )

    assignment_status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus),
        default=AssignmentStatus.active,
        nullable=False,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    released_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )

    # Parent
    work_hours: Mapped[list["WorkHour"]] = relationship(
        back_populates="request_assignment",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Child
    assignee: Mapped["User"] = relationship(
        foreign_keys=[assignee_user_id],
        lazy="raise",
    )


# ===== Work Hour =====
class WorkHour(Base):
    __tablename__ = "work_hours"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_assignment_id: Mapped[str] = mapped_column(
        ForeignKey("request_assignments.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )

    revision_round_id: Mapped[str | None] = mapped_column(
        ForeignKey("revision_rounds.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )

    # Jam desimal, misalnya 1.5.
    hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    work_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # Child
    request_assignment: Mapped["RequestAssignment"] = relationship(
        back_populates="work_hours",
    )



# ===== NC Checklist =====
class NcChecklist(Base):
    """Satu per request per siklus submit. Kolom header sengaja belum ada."""
    __tablename__ = "nc_checklists"
    __table_args__ = (
        # NULL (siklus pertama) dihitung sama, butuh PostgreSQL 15+.
        UniqueConstraint(
            "request_id",
            "revision_round_id",
            name="uq_nc_checklists_request_id_revision_round_id",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_id: Mapped[str] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )

    # Hanya boleh menunjuk putaran origin = japan_correction (aturan aplikasi).
    revision_round_id: Mapped[str | None] = mapped_column(
        ForeignKey("revision_rounds.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
    )

    # Parent
    items: Mapped[list["NcChecklistItem"]] = relationship(
        back_populates="nc_checklist",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )



# ===== NC Checklist Item =====
class NcChecklistItem(Base):
    """step, item, work_type disalin dari master dan SELALU dibaca dari baris ini."""
    __tablename__ = "nc_checklist_items"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    nc_checklist_id: Mapped[str] = mapped_column(
        ForeignKey("nc_checklists.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )

    # Jejak provenance saja.
    source_master_id: Mapped[str | None] = mapped_column(
        ForeignKey("nc_checklist_item_masters.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )

    work_type: Mapped[WorkType] = mapped_column(
        Enum(WorkType),
        nullable=False,
    )

    step: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    item: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    item_status: Mapped[ChecklistItemStatus] = mapped_column(
        Enum(ChecklistItemStatus),
        default=ChecklistItemStatus.pending,
        nullable=False,
    )

    reviewed_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )

    start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Child
    nc_checklist: Mapped["NcChecklist"] = relationship(
        back_populates="items",
    )



# ===== NC Checklist Item Master =====
class NcChecklistItemMaster(Base):
    """Daftar induk per work type, dimiliki superadmin, sama untuk YP dan YS."""
    __tablename__ = "nc_checklist_item_masters"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    work_type: Mapped[WorkType] = mapped_column(
        Enum(WorkType),
        nullable=False,
    )

    step: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    item: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
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