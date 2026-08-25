from collections import Counter, deque
from typing import Iterator, Tuple
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from models.employee import User
from models.attendance import AttendanceLog
from core.logging_config import get_logger

logger = get_logger(__name__)


INGEST_BATCH_SIZE = 500
MAX_RETURNED_LOG_MESSAGES = 200


# ── Shared ingestion core ─────────────────────────────────────

def _ingest_rows(
    rows: Iterator[Tuple],
    session,
    source_label: str,
    progress_signal=None,
) -> Tuple[int, int, int, list]:
    """
    Núcleo compartido de ingesta. Recibe filas ya normalizadas de cualquier fuente.

    Cada fila debe ser una tupla:
        (identifier: str, date: date, time: time, mark_type: int, flags: str)

    PostgreSQL usa ``INSERT ... ON CONFLICT DO NOTHING`` sobre la clave de
    unicidad de ``AttendanceLog``. SQLite conserva una ruta equivalente con
    savepoints. Ambas respetan la clave completa:
    ``(raw_identifier, date, time, mark_type)``.

    Retorna: (nuevos, duplicados, total, logs_msgs)
    """
    nuevos = duplicados = total = 0
    logs_msgs = deque(maxlen=MAX_RETURNED_LOG_MESSAGES)
    is_postgres = session.bind.dialect.name == "postgresql"
    batch: list[Tuple] = []

    def ingest_batch(batch_rows: list[Tuple]) -> list[bool]:
        identifiers = sorted({row[0] for row in batch_rows})

        if is_postgres:
            session.execute(
                pg_insert(User)
                .values([{"identifier": identifier} for identifier in identifiers])
                .on_conflict_do_nothing(index_elements=["identifier"])
            )
        else:
            existing_identifiers = {
                identifier
                for (identifier,) in session.query(User.identifier)
                .filter(User.identifier.in_(identifiers))
                .all()
            }
            session.add_all(
                User(identifier=identifier)
                for identifier in identifiers
                if identifier not in existing_identifiers
            )
            session.flush()

        users_by_identifier = {
            user.identifier: user
            for user in session.query(User).filter(User.identifier.in_(identifiers)).all()
        }
        payloads = [
            {
                "employee_id": users_by_identifier[identifier].id,
                "raw_identifier": identifier,
                "date": log_date,
                "time": log_time,
                "mark_type": mark_type,
                "flags": flags,
                "source_file": source_label,
            }
            for identifier, log_date, log_time, mark_type, flags in batch_rows
        ]

        if is_postgres:
            inserted_keys = Counter(
                tuple(row)
                for row in session.execute(
                    pg_insert(AttendanceLog)
                    .values(payloads)
                    .on_conflict_do_nothing(
                        index_elements=["raw_identifier", "date", "time", "mark_type"]
                    )
                    .returning(
                        AttendanceLog.raw_identifier,
                        AttendanceLog.date,
                        AttendanceLog.time,
                        AttendanceLog.mark_type,
                    )
                ).all()
            )
            inserted = []
            for payload in payloads:
                key = (
                    payload["raw_identifier"],
                    payload["date"],
                    payload["time"],
                    payload["mark_type"],
                )
                inserted.append(inserted_keys[key] > 0)
                inserted_keys[key] -= 1
        else:
            inserted = []
            for payload in payloads:
                try:
                    with session.begin_nested():
                        session.add(AttendanceLog(**payload))
                        session.flush()
                    inserted.append(True)
                except IntegrityError:
                    inserted.append(False)

        session.commit()
        return inserted

    for row in rows:
        if row:
            batch.append(row)
        if len(batch) < INGEST_BATCH_SIZE:
            continue

        inserted_rows = ingest_batch(batch)
        for row, is_new in zip(batch, inserted_rows):
            total += 1
            identifier, log_date, log_time, _, _ = row
            if is_new:
                nuevos += 1
                msg = f"Nuevo log: {identifier} {log_date} {log_time}"
            else:
                duplicados += 1
                msg = f"Duplicado: {identifier} {log_date} {log_time}"
            logs_msgs.append(msg)
            if progress_signal:
                progress_signal.emit(total, nuevos, duplicados, msg)
        batch.clear()

    if batch:
        inserted_rows = ingest_batch(batch)
        for row, is_new in zip(batch, inserted_rows):
            total += 1
            identifier, log_date, log_time, _, _ = row
            if is_new:
                nuevos += 1
                msg = f"Nuevo log: {identifier} {log_date} {log_time}"
            else:
                duplicados += 1
                msg = f"Duplicado: {identifier} {log_date} {log_time}"
            logs_msgs.append(msg)
            if progress_signal:
                progress_signal.emit(total, nuevos, duplicados, msg)

    return nuevos, duplicados, total, list(logs_msgs)


# ── Ingesta desde archivo TXT plano ──────────────────────────

def import_att_logs(
    path: str,
    session,
    progress_signal=None,
    parser=None,
    source_label: str | None = None,
):
    """
    Ingesta desde un archivo TXT plano (upload o USB).
    Usa el parser del addon si se especifica, o el formato SRTime por defecto.
    """
    from services.addons.sundial.parser import SundialParser

    selected_parser = parser or SundialParser()
    logger.info(f"Starting file import: {source_label or path}")

    def _row_generator():
        with open(path, "r", encoding="latin-1") as f:
            for line in f:
                yield selected_parser.parse_line(line)

    nuevos, duplicados, total, logs_msgs = _ingest_rows(
        rows=_row_generator(),
        session=session,
        source_label=source_label or path,
        progress_signal=progress_signal,
    )

    logger.info(f"File import finished: {nuevos} new, {duplicados} duplicates, {total} total")
    return nuevos, duplicados, total, logs_msgs


# ── Ingesta desde dispositivo de red (Pull) ───────────────────

def import_from_driver(driver_instance, connection_params: dict, session, progress_signal=None):
    """
    Ingesta Pull desde cualquier driver de red (ZKTeco, Hikvision, etc.).
    El driver se conecta, descarga los logs y desconecta.
    """
    logger.info(f"Starting device import: {driver_instance.display_name}")
    try:
        if progress_signal:
            progress_signal.emit(0, 0, 0, "Conectando al dispositivo...")
        driver_instance.connect(connection_params)

        known_total = driver_instance.get_attendance_log_count()
        if progress_signal and known_total is not None and hasattr(progress_signal, "set_total"):
            progress_signal.set_total(known_total)

        if progress_signal:
            progress_signal.emit(0, 0, 0, "Descargando registros...")

        result = _ingest_rows(
            rows=driver_instance.get_attendance_logs(),
            session=session,
            source_label=driver_instance.display_name,
            progress_signal=progress_signal,
        )

    except Exception:
        session.rollback()
        logger.exception("Device import failed")
        raise
    finally:
        try:
            driver_instance.disconnect()
        except Exception:
            logger.exception("Device disconnect failed")

    if progress_signal:
        progress_signal.emit(result[2], result[0], result[1], "Completado.")

    logger.info(
        "Device import finished: %s new, %s duplicates, %s total",
        result[0], result[1], result[2],
    )
    return result
