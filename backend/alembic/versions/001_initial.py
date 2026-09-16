"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create all tables via metadata
    from slmforge.db.base import Base
    from slmforge.db.models import dataset, model, experiment, result, artifact, audit  # noqa
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from slmforge.db.base import Base
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
