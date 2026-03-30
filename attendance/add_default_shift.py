from core.database import SessionLocal
from models.shift import Shift
from models.employee import User
from datetime import time

def main():
    session = SessionLocal()
    
    # 1. Crear el turno por defecto si no existe
    default_shift = session.query(Shift).filter_by(name="Turno Administrativo").first()
    
    if not default_shift:
        default_shift = Shift(
            name="Turno Administrativo",
            expected_in=time(9, 0),   # 09:00 AM
            expected_out=time(18, 0), # 06:00 PM
            grace_period_minutes=15   # 15 minutos de tolerancia
        )
        session.add(default_shift)
        session.commit()
        print(f"Turno '{default_shift.name}' creado con éxito.")
    else:
        print(f"El turno '{default_shift.name}' ya existía.")

    # 2. Asignar este turno a todos los usuarios que no tengan turno (shift_id = None)
    usuarios_sin_turno = session.query(User).filter_by(shift_id=None).all()
    count = 0
    for user in usuarios_sin_turno:
        user.shift_id = default_shift.id
        count += 1
        
    if count > 0:
        session.commit()
        print(f"Se asignó el '{default_shift.name}' a {count} usuarios que estaban sin turno.")
    else:
        print("Todos los usuarios ya tenían un turno asignado.")

    session.close()

if __name__ == "__main__":
    main()
