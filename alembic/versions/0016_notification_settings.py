"""notification_settings

Per-type notification settings: new published events (optionally filtered by
tag) and events shared with me.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Opt-in: nobody starts receiving "new event" notifications by surprise.
    inspector = sa.inspect(op.get_bind())
    existing = {c["name"] for c in inspector.get_columns("user")}
    if "notify_new_events" not in existing:
        op.add_column(
            "user",
            sa.Column("notify_new_events", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "notify_event_shared" not in existing:
        op.add_column(
            "user",
            sa.Column("notify_event_shared", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "neweventtagfilter" in inspector.get_table_names():
        return
    op.create_table(
        "neweventtagfilter",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tag.id"]),
        sa.PrimaryKeyConstraint("user_id", "tag_id"),
    )


def downgrade() -> None:
    op.drop_table("neweventtagfilter")
    op.drop_column("user", "notify_event_shared")
    op.drop_column("user", "notify_new_events")
