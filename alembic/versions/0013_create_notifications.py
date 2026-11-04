"""create_notifications

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("link", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_user_id", "notification", ["user_id"])
    op.create_index("ix_notification_event_id", "notification", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_event_id", table_name="notification")
    op.drop_index("ix_notification_user_id", table_name="notification")
    op.drop_table("notification")
