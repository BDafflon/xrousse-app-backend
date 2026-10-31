"""add_tag_famille

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-31 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TAG_FAMILY_VALUES = ("enfant", "famille", "culture", "plein_air", "solidarite", "autre")

# Families for the predefined tags seeded by migration 0002, applied
# retroactively here since those rows predate this column.
PREDEFINED_FAMILIES = {
    "concert": "culture",
    "march": "plein_air",  # slug for "Marché" — accents are stripped, not transliterated
    "atelier": "enfant",
    "exposition": "culture",
    "sport": "plein_air",
    "enfants": "enfant",
    "solidarit": "solidarite",  # slug for "Solidarité" — same stripping behavior
}


def upgrade() -> None:
    tag_family_enum = sa.Enum(*TAG_FAMILY_VALUES, name="tagfamily")
    tag_family_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "tag",
        sa.Column(
            "famille",
            tag_family_enum,
            nullable=False,
            server_default="autre",
        ),
    )

    bind = op.get_bind()
    tag_table = sa.table(
        "tag", sa.column("slug", sa.String()), sa.column("famille", sa.String())
    )
    for slug, famille in PREDEFINED_FAMILIES.items():
        bind.execute(
            tag_table.update().where(tag_table.c.slug == slug).values(famille=famille)
        )


def downgrade() -> None:
    op.drop_column("tag", "famille")
    sa.Enum(name="tagfamily").drop(op.get_bind(), checkfirst=True)
