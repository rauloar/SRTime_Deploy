"""Read-only checks that protect SRTime database upgrades.

Alembic's revision table tells us which migration path to run, but an old or
manually altered database can contain incomplete physical tables.  This module
never changes data: it classifies that situation before an installer creates a
backup or applies a migration.
"""

from __future__ import annotations

from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _expected_schema() -> dict[str, set[str]]:
    """Return the current SRTime ORM contract after registering all models."""
    # init_db imports every model used by the shared schema.  The import is
    # intentional here: metadata must be complete even in the Web executable.
    from core import init_db  # noqa: F401
    from core.database import Base

    return {
        table.name: {column.name for column in table.columns}
        for table in Base.metadata.sorted_tables
    }


def _missing_model_schema(engine: Engine) -> tuple[list[str], dict[str, list[str]]]:
    expected = _expected_schema()
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())
    missing_tables = sorted(set(expected) - actual_tables)
    missing_columns = {
        table_name: sorted(columns - {column["name"] for column in inspector.get_columns(table_name)})
        for table_name, columns in expected.items()
        if table_name in actual_tables
        and columns - {column["name"] for column in inspector.get_columns(table_name)}
    }
    return missing_tables, missing_columns


def _result(
    *,
    state: str,
    compatible: bool,
    message: str,
    tables: set[str],
    current_revision: str | None = None,
    target_heads: list[str] | None = None,
    missing_tables: list[str] | None = None,
    missing_columns: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    return {
        "state": state,
        "compatible": compatible,
        "message": message,
        "current_revision": current_revision,
        "target_heads": target_heads or [],
        "missing_tables": missing_tables or [],
        "missing_columns": missing_columns or {},
        "detected_tables": sorted(tables),
    }


def inspect_upgrade_schema(engine: Engine, alembic_config: Config) -> dict[str, Any]:
    """Classify whether it is safe to run the SRTime Web migration workflow.

    The result is intentionally serializable and contains no connection
    credentials.  A database is accepted only when it is empty, is a complete
    unversioned SRTime schema created by the current wizard, or has a known
    Alembic revision.  A partial unversioned database is blocked rather than
    being stamped at ``head``.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    application_tables = tables - {"alembic_version"}
    expected = _expected_schema()

    if not application_tables:
        return _result(
            state="empty",
            compatible=True,
            message="Empty database: SRTime can create and stamp the current schema.",
            tables=tables,
        )

    missing_tables, missing_columns = _missing_model_schema(engine)
    has_alembic = "alembic_version" in tables
    if not has_alembic:
        if not (set(expected) & application_tables):
            return _result(
                state="foreign_or_unknown",
                compatible=False,
                message="The selected database is not an SRTime database and is not empty.",
                tables=tables,
                missing_tables=missing_tables,
                missing_columns=missing_columns,
            )
        if missing_tables or missing_columns:
            return _result(
                state="unversioned_incomplete",
                compatible=False,
                message=(
                    "SRTime tables were found without Alembic metadata, but their schema "
                    "is incomplete. Automatic update is blocked to avoid stamping an old "
                    "structure as current. Restore or migrate this database manually."
                ),
                tables=tables,
                missing_tables=missing_tables,
                missing_columns=missing_columns,
            )
        return _result(
            state="unversioned_current",
            compatible=True,
            message="Complete unversioned SRTime schema: it can safely be stamped at head.",
            tables=tables,
        )

    with engine.connect() as connection:
        revisions = list(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
    if len(revisions) != 1 or not revisions[0]:
        return _result(
            state="invalid_alembic_metadata",
            compatible=False,
            message="Alembic metadata is invalid: exactly one current revision is required.",
            tables=tables,
            missing_tables=missing_tables,
            missing_columns=missing_columns,
        )

    current_revision = str(revisions[0])
    script = ScriptDirectory.from_config(alembic_config)
    target_heads = sorted(script.get_heads())
    known_revisions = {revision.revision for revision in script.walk_revisions()}
    if current_revision not in known_revisions:
        return _result(
            state="unknown_revision",
            compatible=False,
            message="The database revision is not present in this SRTime release.",
            tables=tables,
            current_revision=current_revision,
            target_heads=target_heads,
            missing_tables=missing_tables,
            missing_columns=missing_columns,
        )

    # A database which claims to be at head must already have the full model
    # contract.  For an older known revision, Alembic owns the incremental path
    # and the final post-migration check enforces this same contract.
    if current_revision in target_heads and (missing_tables or missing_columns):
        return _result(
            state="head_schema_mismatch",
            compatible=False,
            message=(
                "The database claims to be at the current Alembic revision but is missing "
                "SRTime tables or columns. Automatic update is blocked."
            ),
            tables=tables,
            current_revision=current_revision,
            target_heads=target_heads,
            missing_tables=missing_tables,
            missing_columns=missing_columns,
        )

    return _result(
        state="versioned_current" if current_revision in target_heads else "versioned_upgrade_required",
        compatible=True,
        message=(
            "Database is at the current SRTime schema."
            if current_revision in target_heads
            else "Database has a known SRTime revision and can be upgraded by Alembic."
        ),
        tables=tables,
        current_revision=current_revision,
        target_heads=target_heads,
        missing_tables=missing_tables if current_revision in target_heads else [],
        missing_columns=missing_columns if current_revision in target_heads else {},
    )


def assert_complete_model_schema(engine: Engine) -> None:
    """Fail after migration when the physical schema still differs from models."""
    missing_tables, missing_columns = _missing_model_schema(engine)
    if missing_tables or missing_columns:
        raise RuntimeError(
            "Migration finished without the complete SRTime schema: "
            f"missing tables={missing_tables}, missing columns={missing_columns}."
        )
