"""add github column to candidates

El extractor de CVs ya obtiene la URL de GitHub (datos_personales.github,
normalizada por validators.normalize_github) pero se descartaba porque la
tabla candidates no tenía columna. Relevante para vacantes tech.

NOTA: el autogenerate de Alembic detectó "drift" adicional entre los modelos
SQLAlchemy y el schema creado por infra/init-db.sql (índices con otro nombre,
server defaults, JSONB vs JSON, la unique constraint del upsert de matching).
Ese drift es cosmético/intencional y NO debe "corregirse" aquí — borrarlo
rompería el on_conflict_do_update de search.py y los índices de rendimiento.
Esta migración se limita a la columna github.

Revision ID: 77b3274003ed
Revises: 3e09fb20a612
Create Date: 2026-06-11 02:26:47.890179
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '77b3274003ed'
down_revision: Union[str, None] = '3e09fb20a612'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('github', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('candidates', 'github')
