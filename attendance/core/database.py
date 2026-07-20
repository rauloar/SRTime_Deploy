import os
import sys
from sqlalchemy import create_engine
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

DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").lower()

if DB_ENGINE == "postgres":
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASS = os.getenv("DB_PASS", "password")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "srtime_attendance")
    
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(
        DATABASE_URL,
        echo=False
    )
else:
    # Comportamiento por defecto: SQLite
    db_path = os.path.join(base_dir, "attendance.db")
    DATABASE_URL = f"sqlite:///{db_path}"
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()