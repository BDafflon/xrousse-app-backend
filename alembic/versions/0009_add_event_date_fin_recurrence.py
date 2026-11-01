"""add_event_date_fin_recurrence

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("event", sa.Column("date_fin", sa.DateTime(), nullable=True))
    op.add_column("event", sa.Column("recurrence_jours", sa.String(), nullable=True))
    op.add_column("event", sa.Column("recurrence_fin", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("event", "recurrence_fin")
    op.drop_column("event", "recurrence_jours")
    op.drop_column("event", "date_fin")
