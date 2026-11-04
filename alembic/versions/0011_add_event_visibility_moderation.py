"""add_event_visibility_moderation

Adds user-proposed events: `visibilite` (prive/public), `motif_refus`, and
the `en_moderation` / `refuse` values of the `eventstatus` enum.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    visibility = sa.Enum("prive", "public", name="eventvisibility")

    if bind.dialect.name == "postgresql":
        # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE eventstatus ADD VALUE IF NOT EXISTS 'en_moderation'")
            op.execute("ALTER TYPE eventstatus ADD VALUE IF NOT EXISTS 'refuse'")
        visibility.create(bind, checkfirst=True)

    # Existing events were all created by the editorial team: public.
    op.add_column(
        "event",
        sa.Column(
            "visibilite",
            sa.Enum("prive", "public", name="eventvisibility", create_type=False),
            nullable=False,
            server_default="public",
        ),
    )
    op.add_column("event", sa.Column("motif_refus", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("event", "motif_refus")
    op.drop_column("event", "visibilite")
    if op.get_bind().dialect.name == "postgresql":
        sa.Enum(name="eventvisibility").drop(op.get_bind(), checkfirst=True)
    # Enum values added to `eventstatus` cannot be removed in Postgres; the
    # unused values are left in place.
