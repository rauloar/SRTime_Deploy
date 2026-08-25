import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base
from core.config import ATTENDANCE_DIR, load_application_env

# Determinar el directorio correcto donde reside el ejecutable original (o script).
# Soporta: script de desarrollo, binario PyInstaller (sys.frozen) y binario
# Nuitka --standalone (define el global __compiled__, NO setea sys.frozen).
base_dir = str(ATTENDANCE_DIR)
load_application_env()

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
