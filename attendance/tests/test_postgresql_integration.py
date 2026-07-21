"""Integración PostgreSQL opt-in, aislada en un schema transaccional."""

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import Base, engine
from models import attendance, employee, holiday, processed_attendance, shift, terminal, user  # noqa: F401
from models.attendance import AttendanceLog
from services.importer_service import import_att_logs


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1" or engine.dialect.name != "postgresql",
    reason="Requiere RUN_POSTGRES_TESTS=1 y PostgreSQL",
)


MOCK_FILE = Path(__file__).parent / "fixtures" / "tm_mr001_mock.txt"


def test_postgresql_ingestion_is_atomic_and_deduplicated():
    schema = f"srtime_test_{uuid.uuid4().hex}"
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            Base.metadata.create_all(connection)

            session = Session(bind=connection)
            first = import_att_logs(str(MOCK_FILE), session, source_label=MOCK_FILE.name)
            second = import_att_logs(str(MOCK_FILE), session, source_label=MOCK_FILE.name)

            assert first[:3] == (6, 0, 6)
            assert second[:3] == (0, 6, 6)
            assert session.query(AttendanceLog).count() == 6
            assert {row.source_file for row in session.query(AttendanceLog).all()} == {MOCK_FILE.name}
        finally:
            transaction.rollback()
