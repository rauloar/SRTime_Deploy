from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text

from core.database import Base
from core.schema_preflight import inspect_upgrade_schema


def _alembic_config() -> Config:
    project_root = Path(__file__).resolve().parents[2]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    return config


def test_preflight_accepts_empty_database():
    engine = create_engine("sqlite:///:memory:")
    try:
        report = inspect_upgrade_schema(engine, _alembic_config())
        assert report["compatible"] is True
        assert report["state"] == "empty"
    finally:
        engine.dispose()


def test_preflight_blocks_partial_unversioned_schema():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE auth_user (id INTEGER PRIMARY KEY)"))
        report = inspect_upgrade_schema(engine, _alembic_config())
        assert report["compatible"] is False
        assert report["state"] == "unversioned_incomplete"
        assert "auth_user" in report["missing_columns"]
    finally:
        engine.dispose()


def test_preflight_accepts_complete_unversioned_wizard_schema():
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        report = inspect_upgrade_schema(engine, _alembic_config())
        assert report["compatible"] is True
        assert report["state"] == "unversioned_current"
    finally:
        engine.dispose()


def test_preflight_blocks_unknown_alembic_revision():
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('not-a-srtime-revision')"))
        report = inspect_upgrade_schema(engine, _alembic_config())
        assert report["compatible"] is False
        assert report["state"] == "unknown_revision"
    finally:
        engine.dispose()
