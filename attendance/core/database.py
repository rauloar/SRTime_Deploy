import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Determinar el directorio correcto donde reside el ejecutable original (o script).
# Soporta: script de desarrollo, binario PyInstaller (sys.frozen) y binario
# Nuitka --standalone (define el global __compiled__, NO setea sys.frozen).
_is_compiled = getattr(sys, 'frozen', False) or '__compiled__' in globals()

if _is_compiled:
    # Binario compilado: el .env vive junto al ejecutable.
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    # Script de desarrollo: el .env vive en la carpeta attendance/.
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ubicación del .env: override explícito (SRTIME_ENV_FILE) o junto a base_dir.
# Nota: load_dotenv NO pisa variables ya presentes en el entorno (override=False),
# por lo que systemd EnvironmentFile= sigue siendo la fuente de verdad en prod.
env_path = os.environ.get("SRTIME_ENV_FILE") or os.path.join(base_dir, ".env")
load_dotenv(dotenv_path=env_path)

def build_database_url(settings: dict[str, str] | None = None):
    """Build the SQLAlchemy URL from the current environment or explicit settings."""
    source = settings or os.environ
    db_engine = source.get("DB_ENGINE", "sqlite").lower()
    if db_engine == "postgres":
        return URL.create(
            "postgresql",
            username=source.get("DB_USER", "postgres"),
            password=source.get("DB_PASS", ""),
            host=source.get("DB_HOST", "localhost"),
            port=int(source.get("DB_PORT", "5432")),
            database=source.get("DB_NAME", "srtime_db"),
        )

    db_path = source.get("SQLITE_DB_PATH", "attendance.db")
    if not os.path.isabs(db_path):
        db_path = os.path.join(base_dir, db_path)
    return f"sqlite:///{db_path}"


def create_database_engine(database_url):
    is_sqlite = (
        database_url.get_backend_name() == "sqlite"
        if isinstance(database_url, URL)
        else str(database_url).startswith("sqlite")
    )
    if is_sqlite:
        return create_engine(database_url, echo=False, connect_args={"check_same_thread": False})
    return create_engine(database_url, echo=False)


DATABASE_URL = build_database_url()
engine = create_database_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def configure_database(settings: dict[str, str] | None = None):
    """Switch the process to a newly configured database after first-run setup."""
    global DATABASE_URL, engine
    DATABASE_URL = build_database_url(settings)
    engine = create_database_engine(DATABASE_URL)
    SessionLocal.configure(bind=engine)
    return engine
