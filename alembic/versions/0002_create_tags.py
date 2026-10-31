"""create_tags

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-30 00:00:00.000000

"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen as of this migration: do not import app.seed_tags here. That module
# evolves with the live Tag model (e.g. a later migration adds a famille
# column), so calling its seed() from this migration would run the CURRENT
# ORM model against a table shape that only exists as of THIS revision,
# breaking a from-scratch "alembic upgrade head" the moment the model
# changes. Migrations insert fixed data via raw SQL instead.
PREDEFINED_TAGS = ["Concert", "Marché", "Atelier", "Exposition", "Sport", "Enfants", "Solidarité"]


def _slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def upgrade() -> None:
    op.create_table(
        "tag",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nom", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_predefined", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tag_slug"), "tag", ["slug"], unique=True)

    tag_table = sa.table(
        "tag",
        sa.column("nom", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("is_predefined", sa.Boolean()),
    )
    op.bulk_insert(
        tag_table,
        [
            {"nom": nom, "slug": _slugify(nom), "is_predefined": True}
            for nom in PREDEFINED_TAGS
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tag_slug"), table_name="tag")
    op.drop_table("tag")
