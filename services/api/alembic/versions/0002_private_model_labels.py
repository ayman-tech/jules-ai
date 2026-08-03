"""Replace provider-branded model options with Default and Pro."""

import json
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "0002_private_model_labels"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


DEFAULT_MODEL_ID = "gemini-3.5-flash"
PRO_MODEL_ID = "gemini-3.1-pro-preview"
LEGACY_DEFAULT_ID = "gemini-2.5-flash"
LEGACY_PRO_ID = "gemini-2.5-pro"


def _replace_model_ids(default_id: str, pro_id: str, allowed: list[str]) -> None:
    connection = op.get_bind()
    for table_name, column_name in (
        ("conversations", "model"),
        ("user_settings", "default_model"),
        ("organization_model_policies", "default_model"),
    ):
        connection.execute(
            sa.text(f"UPDATE {table_name} SET {column_name} = :default_id WHERE {column_name} = :legacy_default_id"),
            {"default_id": default_id, "legacy_default_id": LEGACY_DEFAULT_ID if default_id == DEFAULT_MODEL_ID else DEFAULT_MODEL_ID},
        )
        connection.execute(
            sa.text(f"UPDATE {table_name} SET {column_name} = :pro_id WHERE {column_name} = :legacy_pro_id"),
            {"pro_id": pro_id, "legacy_pro_id": LEGACY_PRO_ID if pro_id == PRO_MODEL_ID else PRO_MODEL_ID},
        )
    connection.execute(
        sa.text("UPDATE organization_model_policies SET allowed_models_json = :allowed"),
        {"allowed": json.dumps(allowed)},
    )


def upgrade() -> None:
    model_configurations = sa.table(
        "model_configurations",
        sa.column("id", sa.String),
        sa.column("display_name", sa.String),
        sa.column("supports_effort", sa.Boolean),
        sa.column("supports_files", sa.Boolean),
        sa.column("enabled", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    connection = op.get_bind()
    existing = set(connection.execute(sa.text("SELECT id FROM model_configurations WHERE id IN (:default_id, :pro_id)"), {"default_id": DEFAULT_MODEL_ID, "pro_id": PRO_MODEL_ID}).scalars())
    rows = [
        {"id": DEFAULT_MODEL_ID, "display_name": "Default", "supports_effort": True, "supports_files": True, "enabled": True, "created_at": now, "updated_at": now},
        {"id": PRO_MODEL_ID, "display_name": "Pro", "supports_effort": True, "supports_files": True, "enabled": True, "created_at": now, "updated_at": now},
    ]
    missing = [row for row in rows if row["id"] not in existing]
    if missing:
        op.bulk_insert(model_configurations, missing)
    _replace_model_ids(DEFAULT_MODEL_ID, PRO_MODEL_ID, [DEFAULT_MODEL_ID, PRO_MODEL_ID])
    op.execute(sa.text("DELETE FROM model_configurations WHERE id IN ('gemini-2.5-flash', 'gemini-2.5-pro')"))


def downgrade() -> None:
    model_configurations = sa.table(
        "model_configurations",
        sa.column("id", sa.String),
        sa.column("display_name", sa.String),
        sa.column("supports_effort", sa.Boolean),
        sa.column("supports_files", sa.Boolean),
        sa.column("enabled", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(model_configurations, [
        {"id": LEGACY_DEFAULT_ID, "display_name": "Gemini 2.5 Flash", "supports_effort": True, "supports_files": True, "enabled": True, "created_at": now, "updated_at": now},
        {"id": LEGACY_PRO_ID, "display_name": "Gemini 2.5 Pro", "supports_effort": True, "supports_files": True, "enabled": True, "created_at": now, "updated_at": now},
    ])
    _replace_model_ids(LEGACY_DEFAULT_ID, LEGACY_PRO_ID, [LEGACY_DEFAULT_ID, LEGACY_PRO_ID])
    op.execute(sa.text("DELETE FROM model_configurations WHERE id IN ('gemini-3.5-flash', 'gemini-3.1-pro-preview')"))
