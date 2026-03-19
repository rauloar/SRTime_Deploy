from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models.employee import User
from models.attendance import AttendanceLog

def parse_line(line: str):
    identifier = line[0:15]
    fecha_raw  = line[15:21]
    hora_raw   = line[21:25]
    mark_type  = int(line[25:26])
    flags      = line[26:33]

    date = datetime.strptime(fecha_raw, "%d%m%y").date()
    time = datetime.strptime(hora_raw, "%H%M").time()

    return identifier, date, time, mark_type, flags

def import_att_logs(path, session, progress_signal=None):
    nuevos = 0
    duplicados = 0
    total = 0
    logs_msgs = []
    # pointer_date opcional
    import inspect
    pointer_date = None
    # Buscar pointer_date en argumentos si se pasa
    frame = inspect.currentframe()
    try:
        args = frame.f_back.f_locals
        pointer_date = args.get('pointer_date', None)
    finally:
        del frame
    last_log = {}
    for row in session.query(AttendanceLog.raw_identifier, AttendanceLog.date, AttendanceLog.time).order_by(AttendanceLog.raw_identifier, AttendanceLog.date.desc(), AttendanceLog.time.desc()).all():
        if row.raw_identifier not in last_log:
            last_log[row.raw_identifier] = (row.date, row.time)
    # Si pointer_date está definido, ajustar puntero
    if pointer_date:
        for k in last_log:
            if last_log[k][0] < pointer_date:
                last_log[k] = (pointer_date, last_log[k][1])
    with open(path, "r") as f:
        for idx, line in enumerate(f):
            total += 1
            identifier, date, time, mark_type, flags = parse_line(line)
            user = session.query(User).filter_by(identifier=identifier).first()
            if not user:
                user = User(identifier=identifier)
                session.add(user)
                session.commit()
            # Solo guardar si es nuevo
            is_new = False
            if identifier not in last_log:
                is_new = True
            else:
                last_date, last_time = last_log[identifier]
                if (date, time) > (last_date, last_time):
                    is_new = True
            if is_new:
                log = AttendanceLog(
                    employee_id=user.id,
                    raw_identifier=identifier,
                    date=date,
                    time=time,
                    mark_type=mark_type,
                    flags=flags,
                    source_file=path
                )
                session.add(log)
                try:
                    session.commit()
                    nuevos += 1
                    msg = f"Nuevo log: {identifier} {date} {time}"
                    last_log[identifier] = (date, time)
                except IntegrityError:
                    session.rollback()
                    duplicados += 1
                    msg = f"Duplicado: {identifier} {date} {time}"
            else:
                duplicados += 1
                msg = f"Ignorado (ya existe): {identifier} {date} {time}"
            logs_msgs.append(msg)
            if progress_signal:
                progress_signal.emit(total, nuevos, duplicados, msg)
    return nuevos, duplicados, total, logs_msgs