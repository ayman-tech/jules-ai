"""Enable web search by default."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0005_web_search_default"
down_revision = "0004_hashed_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE user_settings SET web_search_default = true"))
    with op.batch_alter_table("user_settings") as batch:
        batch.alter_column(
            "web_search_default",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=sa.true(),
        )


def downgrade() -> None:
    with op.batch_alter_table("user_settings") as batch:
        batch.alter_column(
            "web_search_default",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=sa.false(),
        )
