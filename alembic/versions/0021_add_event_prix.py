"""add_event_prix_min_max

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("event")}
    # An earlier version of this migration added a single `prix` column.
    if "prix" in cols and "prix_min" not in cols:
        op.alter_column("event", "prix", new_column_name="prix_min")
        cols = (cols - {"prix"}) | {"prix_min"}
    if "prix_min" not in cols:
        op.add_column("event", sa.Column("prix_min", sa.Float(), nullable=True))
    if "prix_max" not in cols:
        op.add_column("event", sa.Column("prix_max", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("event", "prix_max")
    op.drop_column("event", "prix_min")
