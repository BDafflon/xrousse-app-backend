"""create_event_shares

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eventshare",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "event_id", name="uq_event_share_user_event"),
    )
    op.create_index("ix_eventshare_user_id", "eventshare", ["user_id"])
    op.create_index("ix_eventshare_event_id", "eventshare", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_eventshare_event_id", table_name="eventshare")
    op.drop_index("ix_eventshare_user_id", table_name="eventshare")
    op.drop_table("eventshare")
