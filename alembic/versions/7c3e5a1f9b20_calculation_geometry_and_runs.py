"""calculation geometry and runs

Geometri tiang dan objek langsung dibentuk ulang dengan nama dan satuan
kontrak engine, katalog taper mendapat geometri per pilihan tinggi, tabel
hasil dicabut, dan calculation_runs menyimpan jawaban engine apa adanya.

Tabel case yang dibentuk ulang belum pernah ditulis kode mana pun, sehingga
dibuat ulang (drop + create) tanpa memindahkan data. Migration menolak jalan
bila salah satunya berisi.

Revision ID: 7c3e5a1f9b20
Revises: 1f1e799dabf3
Create Date: 2026-10-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7c3e5a1f9b20'
down_revision: Union[str, Sequence[str], None] = '1f1e799dabf3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# create_type=False: tipe dibuat sekali di awal upgrade, bukan oleh tiap create_table.
POLE_TYPE = postgresql.ENUM('taper', 'straight', name='poletype', create_type=False)
OBJECT_KIND = postgresql.ENUM('omni', 'directional', name='objectkind', create_type=False)
RUN_TYPE = postgresql.ENUM('pole', name='calculationruntype', create_type=False)
NUM = sa.Numeric(precision=10, scale=5)

POLE_SEGMENT_CHECK = (
    "(pole_type = 'straight' AND diameter_upper_mm IS NULL AND thickness_upper_mm IS NULL)"
    " OR (pole_type = 'taper' AND diameter_upper_mm IS NOT NULL AND thickness_upper_mm IS NOT NULL)"
)
OBJECT_KIND_CHECK = (
    "(object_kind = 'omni' AND side_area_m2 IS NULL AND fixed_angle_deg IS NULL)"
    " OR (object_kind = 'directional' AND side_area_m2 IS NOT NULL AND fixed_angle_deg IS NOT NULL)"
)


def _ensure_empty(tables: tuple[str, ...]) -> None:
    bind = op.get_bind()
    for table in tables:
        count = bind.execute(sa.text(f'SELECT count(*) FROM "{table}"')).scalar_one()
        if count:
            raise RuntimeError(
                f"{table} berisi {count} baris. Migration ini membuat ulang tabel tanpa "
                "memindahkan data. Kosongkan dulu atau reset schema (lihat plan, Lampiran A)."
            )


def _segment_columns() -> list:
    return [
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('pole_type', POLE_TYPE, nullable=False),
        sa.Column('top_elevation_m', NUM, nullable=False),
        sa.Column('diameter_lower_mm', NUM, nullable=False),
        sa.Column('diameter_upper_mm', NUM, nullable=True),
        sa.Column('thickness_lower_mm', NUM, nullable=False),
        sa.Column('thickness_upper_mm', NUM, nullable=True),
    ]


def _segment_constraints(table: str, parent: str) -> list:
    return [
        sa.CheckConstraint(POLE_SEGMENT_CHECK, name=op.f(f'ck_{table}_pole_type_dimensions')),
        sa.UniqueConstraint(parent, 'name', name=f'uq_{table}_name'),
        sa.UniqueConstraint(parent, 'top_elevation_m', name=f'uq_{table}_top_elevation_m'),
    ]


def _direct_object_columns() -> list:
    return [
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('object_kind', OBJECT_KIND, nullable=False),
        sa.Column('front_area_m2', NUM, nullable=False),
        sa.Column('side_area_m2', NUM, nullable=True),
        sa.Column('fixed_angle_deg', NUM, nullable=True),
        sa.Column('mass_per_unit_kg', NUM, nullable=False),
        sa.Column('elevation_m', NUM, nullable=False),
        sa.Column('base_wind_coefficient', NUM, nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
    ]


def _direct_object_constraints(table: str, parent: str) -> list:
    return [
        sa.CheckConstraint(OBJECT_KIND_CHECK, name=op.f(f'ck_{table}_object_kind_dimensions')),
        sa.UniqueConstraint(parent, 'name', name=f'uq_{table}_name'),
    ]


def upgrade() -> None:
    """Upgrade schema."""
    _ensure_empty((
        'pole_results', 'direct_object_results', 'calculation_results',
        'step_poles', 'direct_objects', 'drawing_step_poles', 'calculation_runs',
    ))

    # Nilai enum baru harus di-commit sebelum dipakai (CHECK status_snapshot memakainya),
    # jadi ALTER TYPE dijalankan di luar transaksi migration.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE statuscalculationrun ADD VALUE IF NOT EXISTS 'failed'")

    bind = op.get_bind()
    for enum_type in (POLE_TYPE, OBJECT_KIND, RUN_TYPE):
        enum_type.create(bind, checkfirst=True)

    # ===== Tabel hasil dicabut =====
    op.drop_table('pole_results')
    op.drop_table('direct_object_results')
    op.drop_table('calculation_results')

    # ===== Geometri case dibuat ulang =====
    op.drop_table('step_poles')
    op.create_table('step_poles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('calculation_case_id', sa.String(), nullable=False),
        sa.Column('material_id', sa.String(), nullable=False),
        *_segment_columns(),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['calculation_case_id'], ['calculation_cases.id'], name=op.f('fk_step_poles_calculation_case_id_calculation_cases'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], name=op.f('fk_step_poles_material_id_materials'), onupdate='CASCADE', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_step_poles')),
        *_segment_constraints('step_poles', 'calculation_case_id'),
    )

    op.drop_table('drawing_step_poles')
    op.create_table('drawing_step_poles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('drawing_case_id', sa.String(), nullable=False),
        sa.Column('material_id', sa.String(), nullable=False),
        *_segment_columns(),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['drawing_case_id'], ['drawing_cases.id'], name=op.f('fk_drawing_step_poles_drawing_case_id_drawing_cases'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], name=op.f('fk_drawing_step_poles_material_id_materials'), onupdate='CASCADE', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_drawing_step_poles')),
        *_segment_constraints('drawing_step_poles', 'drawing_case_id'),
    )

    op.drop_table('direct_objects')
    op.create_table('direct_objects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('calculation_case_id', sa.String(), nullable=False),
        *_direct_object_columns(),
        sa.ForeignKeyConstraint(['calculation_case_id'], ['calculation_cases.id'], name=op.f('fk_direct_objects_calculation_case_id_calculation_cases'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_direct_objects')),
        *_direct_object_constraints('direct_objects', 'calculation_case_id'),
    )

    # ===== calculation_runs: tabel kosong, kolom not null aman ditambah =====
    op.add_column('calculation_runs', sa.Column('run_type', RUN_TYPE, nullable=False))
    op.add_column('calculation_runs', sa.Column('parent_run_id', sa.String(), nullable=True))
    op.add_column('calculation_runs', sa.Column('result_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('calculation_runs', sa.Column('error_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('calculation_runs', sa.Column('run_by_user_id', sa.String(), nullable=False))
    op.alter_column('calculation_runs', 'input_snapshot', existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=False)
    op.create_unique_constraint('uq_calculation_runs_id_calculation_case_id', 'calculation_runs', ['id', 'calculation_case_id'])
    op.create_foreign_key(
        op.f('fk_calculation_runs_parent_run_id_calculation_runs'), 'calculation_runs', 'calculation_runs',
        ['parent_run_id', 'calculation_case_id'], ['id', 'calculation_case_id'],
        onupdate='CASCADE', ondelete='CASCADE',
    )
    op.create_foreign_key(
        op.f('fk_calculation_runs_run_by_user_id_users'), 'calculation_runs', 'users',
        ['run_by_user_id'], ['id'], onupdate='CASCADE', ondelete='RESTRICT',
    )
    op.create_check_constraint(
        op.f('ck_calculation_runs_run_type_parent'), 'calculation_runs',
        "run_type <> 'pole' OR parent_run_id IS NULL",
    )
    op.create_check_constraint(
        op.f('ck_calculation_runs_status_snapshot'), 'calculation_runs',
        "(status = 'failed') = (result_snapshot IS NULL) AND (status = 'failed') = (error_snapshot IS NOT NULL)",
    )

    # ===== Kolom tambahan =====
    op.add_column('calculation_cases', sa.Column('evaluated_positions_m', postgresql.ARRAY(NUM), nullable=True))
    op.add_column('design_standards', sa.Column('code', sa.Integer(), nullable=True))
    op.drop_column('pole_standards', 'geometry')
    op.add_column('pole_standard_heights', sa.Column('evaluated_positions_m', postgresql.ARRAY(NUM), nullable=True))
    op.add_column('pole_standard_heights', sa.Column('gl_elevation_m', NUM, nullable=True))

    # ===== Katalog geometri per pilihan tinggi =====
    op.create_table('pole_standard_segments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('pole_standard_height_id', sa.String(), nullable=False),
        sa.Column('material_id', sa.String(), nullable=False),
        *_segment_columns(),
        sa.ForeignKeyConstraint(['pole_standard_height_id'], ['pole_standard_heights.id'], name=op.f('fk_pole_standard_segments_pole_standard_height_id_pole_standard_heights'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], name=op.f('fk_pole_standard_segments_material_id_materials'), onupdate='CASCADE', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_pole_standard_segments')),
        *_segment_constraints('pole_standard_segments', 'pole_standard_height_id'),
    )
    op.create_table('pole_standard_direct_objects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('pole_standard_height_id', sa.String(), nullable=False),
        *_direct_object_columns(),
        sa.ForeignKeyConstraint(['pole_standard_height_id'], ['pole_standard_heights.id'], name=op.f('fk_pole_standard_direct_objects_pole_standard_height_id_pole_standard_heights'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_pole_standard_direct_objects')),
        *_direct_object_constraints('pole_standard_direct_objects', 'pole_standard_height_id'),
    )


def downgrade() -> None:
    """Downgrade schema.

    Isi katalog geometri (seed) ikut hilang dan bisa di-seed ulang. Data case
    tidak dipindahkan, sehingga tabel case harus kosong. Nilai enum 'failed'
    tetap ada di statuscalculationrun, karena PostgreSQL tidak bisa mencabut
    nilai enum; nilai itu tidak dipakai skema lama.
    """
    _ensure_empty(('step_poles', 'direct_objects', 'drawing_step_poles', 'calculation_runs'))

    op.drop_table('pole_standard_direct_objects')
    op.drop_table('pole_standard_segments')
    op.drop_column('pole_standard_heights', 'gl_elevation_m')
    op.drop_column('pole_standard_heights', 'evaluated_positions_m')
    op.add_column('pole_standards', sa.Column('geometry', sa.JSON(), nullable=True))
    op.drop_column('design_standards', 'code')
    op.drop_column('calculation_cases', 'evaluated_positions_m')

    op.drop_constraint(op.f('ck_calculation_runs_status_snapshot'), 'calculation_runs', type_='check')
    op.drop_constraint(op.f('ck_calculation_runs_run_type_parent'), 'calculation_runs', type_='check')
    op.drop_constraint(op.f('fk_calculation_runs_run_by_user_id_users'), 'calculation_runs', type_='foreignkey')
    op.drop_constraint(op.f('fk_calculation_runs_parent_run_id_calculation_runs'), 'calculation_runs', type_='foreignkey')
    op.drop_constraint('uq_calculation_runs_id_calculation_case_id', 'calculation_runs', type_='unique')
    op.alter_column('calculation_runs', 'input_snapshot', existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    op.drop_column('calculation_runs', 'run_by_user_id')
    op.drop_column('calculation_runs', 'error_snapshot')
    op.drop_column('calculation_runs', 'result_snapshot')
    op.drop_column('calculation_runs', 'parent_run_id')
    op.drop_column('calculation_runs', 'run_type')

    # Bentuk lama, persis seperti baseline 1f1e799dabf3.
    op.drop_table('direct_objects')
    op.create_table('direct_objects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('calculation_case_id', sa.String(), nullable=False),
        sa.Column('object_type_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('front_area', NUM, nullable=False),
        sa.Column('height', NUM, nullable=False),
        sa.Column('nnc', NUM, nullable=False),
        sa.Column('weight', NUM, nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['calculation_case_id'], ['calculation_cases.id'], name=op.f('fk_direct_objects_calculation_case_id_calculation_cases'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['object_type_id'], ['object_types.id'], name=op.f('fk_direct_objects_object_type_id_object_types'), onupdate='CASCADE', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_direct_objects'))
    )
    for table, parent, parent_table in (
        ('step_poles', 'calculation_case_id', 'calculation_cases'),
        ('drawing_step_poles', 'drawing_case_id', 'drawing_cases'),
    ):
        op.drop_table(table)
        op.create_table(table,
            sa.Column('id', sa.String(), nullable=False),
            sa.Column(parent, sa.String(), nullable=False),
            sa.Column('material_id', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('order', sa.Integer(), nullable=False),
            sa.Column('diameter', NUM, nullable=False),
            sa.Column('thickness', NUM, nullable=False),
            sa.Column('height', NUM, nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint([parent], [f'{parent_table}.id'], name=op.f(f'fk_{table}_{parent}_{parent_table}'), onupdate='CASCADE', ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['material_id'], ['materials.id'], name=op.f(f'fk_{table}_material_id_materials'), onupdate='CASCADE', ondelete='RESTRICT'),
            sa.PrimaryKeyConstraint('id', name=op.f(f'pk_{table}'))
        )

    op.create_table('calculation_results',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('calculation_run_id', sa.String(), nullable=False),
        sa.Column('total_moment', NUM, nullable=False),
        sa.Column('total_windload', NUM, nullable=False),
        sa.Column('status', postgresql.ENUM('ok', 'ng', 'failed', name='statuscalculationrun', create_type=False), nullable=False),
        sa.ForeignKeyConstraint(['calculation_run_id'], ['calculation_runs.id'], name=op.f('fk_calculation_results_calculation_run_id_calculation_runs'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_calculation_results'))
    )
    op.create_table('direct_object_results',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('direct_object_id', sa.String(), nullable=False),
        sa.Column('calculation_result_id', sa.String(), nullable=False),
        sa.Column('windload', NUM, nullable=False),
        sa.Column('moment', NUM, nullable=False),
        sa.ForeignKeyConstraint(['calculation_result_id'], ['calculation_results.id'], name=op.f('fk_direct_object_results_calculation_result_id_calculation_results'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['direct_object_id'], ['direct_objects.id'], name=op.f('fk_direct_object_results_direct_object_id_direct_objects'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_direct_object_results'))
    )
    op.create_table('pole_results',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('step_pole_id', sa.String(), nullable=False),
        sa.Column('calculation_result_id', sa.String(), nullable=False),
        sa.Column('windload', NUM, nullable=False),
        sa.Column('moment', NUM, nullable=False),
        sa.ForeignKeyConstraint(['calculation_result_id'], ['calculation_results.id'], name=op.f('fk_pole_results_calculation_result_id_calculation_results'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_pole_id'], ['step_poles.id'], name=op.f('fk_pole_results_step_pole_id_step_poles'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_pole_results'))
    )

    bind = op.get_bind()
    for enum_type in (RUN_TYPE, OBJECT_KIND, POLE_TYPE):
        enum_type.drop(bind, checkfirst=True)