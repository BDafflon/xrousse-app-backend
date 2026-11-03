"""create_saved_events

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "savedevent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "event_id", name="uq_saved_event_user_event"),
    )
    op.create_index("ix_savedevent_user_id", "savedevent", ["user_id"])
    op.create_index("ix_savedevent_event_id", "savedevent", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_savedevent_event_id", table_name="savedevent")
    op.drop_index("ix_savedevent_user_id", table_name="savedevent")
    op.drop_table("savedevent")
