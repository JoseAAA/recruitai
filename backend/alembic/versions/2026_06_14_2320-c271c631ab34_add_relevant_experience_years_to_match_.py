"""add relevant_experience_years to match_results

Revision ID: c271c631ab34
Revises: b8f2a1c9d4e7
Create Date: 2026-06-14 23:20:30.495742
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c271c631ab34'
down_revision: Union[str, None] = 'b8f2a1c9d4e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # El modelo MatchResultDB declaraba `relevant_experience_years` pero ninguna
    # migración (ni init-db.sql) creaba la columna → en BD fresca la tabla salía
    # sin ella y GET /api/jobs/{id}/scores fallaba con 500
    # (UndefinedColumnError). Esta migración la agrega para alinear BD y modelo.
    op.add_column(
        "match_results",
        sa.Column("relevant_experience_years", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("match_results", "relevant_experience_years")
