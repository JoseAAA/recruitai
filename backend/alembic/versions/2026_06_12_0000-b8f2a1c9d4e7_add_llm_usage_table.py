"""add llm_usage table

Tabla de consumo del LLM por operación (extracción de CV, matching, explicación
al candidato, análisis de vacante). Guarda los tokens reales reportados por la
API del proveedor + la latencia medida en el servidor, con contexto de negocio
(candidato, vacante, usuario, batch de matching). Es la base de los KPIs/OKRs y
del costeo que expone el panel /admin/usage.

Diseño write-only/analytics (igual que audit_logs): candidate_id y job_id son
UUID nullable SIN ForeignKey, para que borrar un candidato/vacante (derecho
ARCO-P) nunca elimine el historial de consumo ni falle por constraint.

Revision ID: b8f2a1c9d4e7
Revises: 77b3274003ed
Create Date: 2026-06-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

# revision identifiers, used by Alembic.
revision: str = 'b8f2a1c9d4e7'
down_revision: Union[str, None] = '77b3274003ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'llm_usage',
        sa.Column('id', PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            'created_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('operation', sa.String(length=20), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('model', sa.String(length=80), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('preprocess_ms', sa.Integer(), nullable=True),
        sa.Column('candidate_id', PGUUID(as_uuid=True), nullable=True),
        sa.Column('job_id', PGUUID(as_uuid=True), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('batch_id', PGUUID(as_uuid=True), nullable=True),
        sa.Column('success', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('error_type', sa.String(length=80), nullable=True),
    )
    op.create_index('ix_llm_usage_created_at', 'llm_usage', ['created_at'])
    op.create_index('ix_llm_usage_operation', 'llm_usage', ['operation'])
    op.create_index('ix_llm_usage_provider', 'llm_usage', ['provider'])
    op.create_index('ix_llm_usage_candidate_id', 'llm_usage', ['candidate_id'])
    op.create_index('ix_llm_usage_job_id', 'llm_usage', ['job_id'])
    op.create_index('ix_llm_usage_batch_id', 'llm_usage', ['batch_id'])


def downgrade() -> None:
    op.drop_index('ix_llm_usage_batch_id', table_name='llm_usage')
    op.drop_index('ix_llm_usage_job_id', table_name='llm_usage')
    op.drop_index('ix_llm_usage_candidate_id', table_name='llm_usage')
    op.drop_index('ix_llm_usage_provider', table_name='llm_usage')
    op.drop_index('ix_llm_usage_operation', table_name='llm_usage')
    op.drop_index('ix_llm_usage_created_at', table_name='llm_usage')
    op.drop_table('llm_usage')
