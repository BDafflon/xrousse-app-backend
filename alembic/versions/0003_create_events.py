"""create_events

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titre", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("source_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=True),
        sa.Column("lieu", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("image_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "statut",
            sa.Enum("brouillon", "publie", name="eventstatus"),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("likes_count", sa.Integer(), nullable=False),
        sa.Column("featured_editorial", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_event_source_url"), "event", ["source_url"], unique=True
    )

    op.create_table(
        "eventtag",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tag.id"]),
        sa.PrimaryKeyConstraint("event_id", "tag_id"),
    )


def downgrade() -> None:
    op.drop_table("eventtag")
    op.drop_index(op.f("ix_event_source_url"), table_name="event")
    op.drop_table("event")
