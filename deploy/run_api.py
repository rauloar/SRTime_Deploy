"""Entry point para la compilación con Nuitka.
Carga FastAPI y uvicorn para ejecutarse como binario independiente.
"""
import os
import sys
import uvicorn
from multiprocessing import freeze_support

# Cuando Nuitka o PyInstaller compilan el programa, se ajusta el CWD
if getattr(sys, 'frozen', False) or '__compiled__' in globals():
    base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    os.chdir(base_path)
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
else:
    # Development mode: attendance folder
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    attendance_path = os.path.join(base_path, 'attendance')
    if attendance_path not in sys.path:
        sys.path.insert(0, attendance_path)


def _truthy(val: str) -> bool:
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def run_db_bootstrap() -> None:
    """Inicializa la base de datos para un deploy compilado (sin código fuente).

    Crea el esquema completo (create_all) y siembra el admin vía
    core.init_db.init_database(). Luego intenta 'alembic stamp head' como
    bookkeeping — best-effort: en el binario alembic.ini puede no estar, y para
    una instalación fresca create_all ya deja el esquema en su estado actual.
    Pensado para ejecutarse UNA vez: RUN_DB_BOOTSTRAP=1 <binario>.
    """
    from core.init_db import init_database

    print("[bootstrap] Inicializando esquema y admin...", flush=True)
    init_database()
    print("[bootstrap] Esquema + admin OK.", flush=True)

    # alembic stamp head (best-effort): solo si encontramos alembic.ini.
    ini_candidates = [
        os.path.join(base_path, "alembic.ini"),
        os.path.join(os.path.dirname(base_path), "alembic.ini"),
    ]
    ini_path = next((p for p in ini_candidates if os.path.isfile(p)), None)
    if ini_path:
        try:
            from alembic.config import Config
            from alembic import command
            command.stamp(Config(ini_path), "head")
            print("[bootstrap] alembic stamp head OK.", flush=True)
        except Exception as exc:  # noqa: BLE001 — bootstrap no debe fallar por esto
            print(f"[bootstrap] alembic stamp omitido ({exc}).", flush=True)
    else:
        print("[bootstrap] alembic.ini no encontrado — stamp omitido "
              "(create_all es la fuente del esquema en deploy compilado).", flush=True)


# Se importa la app luego de ajustar el path
from api.main_api import app

if __name__ == "__main__":
    freeze_support()

    # Modo one-shot: inicializar la DB y salir (no levanta el servidor).
    if _truthy(os.environ.get("RUN_DB_BOOTSTRAP", "")):
        run_db_bootstrap()
        sys.exit(0)

    uvicorn.run(
        app,
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "8000")),
        workers=int(os.environ.get("API_WORKERS", "4")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
