"""drop opening_direction from calculation_openings

Revision ID: 2628cada897e
Revises: 34873a55d6c8
Create Date: 2026-09-09 15:53:43.936587

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2628cada897e'
down_revision: Union[str, Sequence[str], None] = '34873a55d6c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop kolom opening_direction dari calculation_openings.
    Enum type 'openingdirection' TIDAK disentuh — masih dipakai drawing_openings.
    """
    with op.batch_alter_table("calculation_openings") as batch_op:
        batch_op.drop_column("opening_direction")


def downgrade() -> None:
    """Re-add kolom. Nilai lama tidak dapat dipulihkan (hilang saat drop) →
    dibuat nullable=True. Di Postgres, reuse type yang sudah ada (jangan CREATE).
    """
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        col_type = postgresql.ENUM(
            "left", "right", "front", "back",
            name="openingdirection",
            create_type=False,   # type masih dipakai drawing_openings → jangan buat ulang
        )
    else:
        col_type = sa.Enum("left", "right", "front", "back", name="openingdirection")

    with op.batch_alter_table("calculation_openings") as batch_op:
        batch_op.add_column(
            sa.Column("opening_direction", col_type, nullable=True)
        )
