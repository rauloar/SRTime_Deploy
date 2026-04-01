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

# Se importa la app luego de ajustar el path
from api.main_api import app

if __name__ == "__main__":
    freeze_support()
    uvicorn.run(
        app,
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "8000")),
        workers=int(os.environ.get("API_WORKERS", "4")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
