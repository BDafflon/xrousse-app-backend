"""add_tag_is_deleted

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "is_deleted" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("tag")}:
        return
    op.add_column(
        "tag",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("tag", "is_deleted")
