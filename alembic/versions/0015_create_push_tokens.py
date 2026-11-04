"""create_push_tokens

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "pushtoken" in inspector.get_table_names():
        existing = {i["name"] for i in inspector.get_indexes("pushtoken")}
        if "ix_pushtoken_user_id" not in existing:
            op.create_index("ix_pushtoken_user_id", "pushtoken", ["user_id"])
        if "ix_pushtoken_token" not in existing:
            op.create_index("ix_pushtoken_token", "pushtoken", ["token"], unique=True)
        return

    op.create_table(
        "pushtoken",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("platform", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pushtoken_user_id", "pushtoken", ["user_id"])
    op.create_index("ix_pushtoken_token", "pushtoken", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_pushtoken_token", table_name="pushtoken")
    op.drop_index("ix_pushtoken_user_id", table_name="pushtoken")
    op.drop_table("pushtoken")
