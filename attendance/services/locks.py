"""Exclusión entre procesos con el mismo resultado en PostgreSQL y SQLite.

La Web (PostgreSQL) puede compartir la base con uno o más Desktop: una descarga
o el programador de terminales no deben correr dos veces a la vez sobre lo
mismo (un módulo Tibbo acepta una sola conexión). En PostgreSQL se usa un
advisory lock de transacción, que vale entre procesos y PCs y se libera solo
si el proceso muere. SQLite es de un único proceso (Desktop): alcanza un lock
en memoria por nombre.
"""
from __future__ import annotations

import zlib
from contextlib import contextmanager
from threading import Lock

from sqlalchemy import text

_local_guard = Lock()
_local_locks: dict[tuple[str, int], Lock] = {}


def _namespace(name: str) -> int:
    # pg_try_advisory_xact_lock(int4, int4): el nombre se reduce a un int4 estable.
    return zlib.crc32(name.encode("utf-8")) & 0x7FFFFFFF


@contextmanager
def try_exclusive(bind, name: str, key: int = 0):
    """``with try_exclusive(engine, "terminal-pull", 5) as acquired:`` — no espera.

    ``acquired`` es False si otro proceso (o hilo) ya lo tiene; el bloque igual
    se ejecuta y decide qué hacer.
    """
    if bind.dialect.name == "postgresql":
        with bind.connect() as connection:
            with connection.begin():
                acquired = bool(connection.execute(
                    text("SELECT pg_try_advisory_xact_lock(:namespace, :key)"),
                    {"namespace": _namespace(name), "key": int(key)},
                ).scalar())
                yield acquired
        return

    with _local_guard:
        lock = _local_locks.setdefault((name, int(key)), Lock())
    acquired = lock.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()
