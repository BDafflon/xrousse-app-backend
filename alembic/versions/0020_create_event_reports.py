"""create_event_reports

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eventreport",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("reporter_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"]),
        sa.ForeignKeyConstraint(["reporter_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eventreport_event_id", "eventreport", ["event_id"])
    op.create_index("ix_eventreport_reporter_id", "eventreport", ["reporter_id"])
    op.create_index("ix_eventreport_resolved", "eventreport", ["resolved"])


def downgrade() -> None:
    op.drop_index("ix_eventreport_resolved", table_name="eventreport")
    op.drop_index("ix_eventreport_reporter_id", table_name="eventreport")
    op.drop_index("ix_eventreport_event_id", table_name="eventreport")
    op.drop_table("eventreport")
