"""cache candidate-facing explanation on match_results

Revision ID: a1b2c3d4e5f6
Revises: c271c631ab34
Create Date: 2026-07-04 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'c271c631ab34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cachea la explicación al candidato (derecho a explicación DS 115-2025-PCM)
    # en la propia fila del match para no re-llamar al LLM en cada solicitud del
    # mismo par candidato-vacante. `explanation_candidate_at` permite invalidar
    # el caché cuando el match se vuelve a puntuar (scored_at avanza).
    op.add_column(
        "match_results",
        sa.Column("explanation_candidate", sa.Text(), nullable=True),
    )
    op.add_column(
        "match_results",
        sa.Column(
            "explanation_candidate_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("match_results", "explanation_candidate_at")
    op.drop_column("match_results", "explanation_candidate")
