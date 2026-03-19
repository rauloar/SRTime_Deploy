import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base_dir, ".env")
    
    if not os.path.exists(env_path):
        print("Error: El archivo .env no existe. Rellénalo primero.")
        return

    load_dotenv(env_path)

    engine = os.getenv("DB_ENGINE", "sqlite").lower()
    if engine != "postgres":
        print(f"Advertencia: DB_ENGINE está en '{engine}', debe ser 'postgres' para correr este script.")
        return

    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASS", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "attendance")

    if password == "escribe_tu_contraseña_aqui" or password == "":
        print("ERROR: Por favor edita el archivo .env y pon la contraseña real de PostgreSQL de tu PC local.")
        return

    print(f"Conectando a PostgreSQL ({host}:{port}) con el usuario '{user}'...")
    try:
        # 1. Conectarnos a la base de datos de sistema para poder crear la nuestra
        conn = psycopg2.connect(user=user, password=password, host=host, port=port, dbname="postgres")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # 2. Verificamos si existe y si no la creamos
        cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{dbname}'")
        exists = cursor.fetchone()

        if not exists:
            print(f"--- Creando la base de datos '{dbname}' ---")
            cursor.execute(f"CREATE DATABASE {dbname};")
        else:
            print(f"--- La base de datos '{dbname}' ya existía ---")
            
        cursor.close()
        conn.close()

        # 3. Mandamos a inicializar las tablas con SQLAlchemy
        print("--- Construyendo tablas y usuario admin mediante SQLAlchemy ---")
        from core.init_db import init_database
        init_database()
        print("¡TODO LISTO! La base de datos PostgreSQL y todas las tablas de asistencia han sido construidas. Ya puedes usar `python main.py`.")

    except psycopg2.OperationalError as e:
        print(f"\n[!] ERROR DE CONEXIÓN: Verifica los datos en el .env o asegúrate de que el servicio PostgreSQL esté encendido.\n[Detalle del error]: {e}")
    except Exception as e:
        print(f"\n[!] ERROR INESPERADO: {e}")

if __name__ == "__main__":
    main()
