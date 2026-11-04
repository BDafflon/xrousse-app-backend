"""add_event_views_count

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "views_count" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("event")}:
        return
    op.add_column(
        "event",
        sa.Column("views_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("event", "views_count")
