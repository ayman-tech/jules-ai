"""Store invitation secrets as SHA-256 hashes."""

from __future__ import annotations

import hashlib

import sqlalchemy as sa
from alembic import op


revision = "0004_hashed_invitations"
down_revision = "0003_second_brain"
branch_labels = None
depends_on = None


TABLE = "organization_invitations"


def _columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}


def _has_unique(column: str) -> bool:
    constraints = sa.inspect(op.get_bind()).get_unique_constraints(TABLE)
    return any(item.get("column_names") == [column] for item in constraints)


def upgrade() -> None:
    columns = _columns()
    if "token_hash" not in columns:
        with op.batch_alter_table(TABLE) as batch:
            batch.add_column(sa.Column("token_hash", sa.String(length=64), nullable=True))

    connection = op.get_bind()
    columns = _columns()
    if "token" in columns:
        rows = connection.execute(sa.text(f"SELECT id, token FROM {TABLE} WHERE token_hash IS NULL")).mappings()
        for row in rows:
            digest = hashlib.sha256(row["token"].encode("utf-8")).hexdigest()
            connection.execute(
                sa.text(f"UPDATE {TABLE} SET token_hash = :digest WHERE id = :id"),
                {"digest": digest, "id": row["id"]},
            )

    with op.batch_alter_table(TABLE) as batch:
        batch.alter_column("token_hash", existing_type=sa.String(length=64), nullable=False)
        if not _has_unique("token_hash"):
            batch.create_unique_constraint("uq_organization_invitations_token_hash", ["token_hash"])
        if "token" in columns:
            batch.drop_column("token")


def downgrade() -> None:
    columns = _columns()
    with op.batch_alter_table(TABLE) as batch:
        if "token" not in columns:
            batch.add_column(sa.Column("token", sa.String(length=96), nullable=True))

    connection = op.get_bind()
    connection.execute(sa.text(f"UPDATE {TABLE} SET token = token_hash WHERE token IS NULL"))
    token_hash_constraint = next(
        (
            item.get("name")
            for item in sa.inspect(connection).get_unique_constraints(TABLE)
            if item.get("column_names") == ["token_hash"]
        ),
        None,
    )
    with op.batch_alter_table(TABLE) as batch:
        batch.alter_column("token", existing_type=sa.String(length=96), nullable=False)
        if not _has_unique("token"):
            batch.create_unique_constraint("uq_organization_invitations_token", ["token"])
        if token_hash_constraint:
            batch.drop_constraint(token_hash_constraint, type_="unique")
        batch.drop_column("token_hash")
