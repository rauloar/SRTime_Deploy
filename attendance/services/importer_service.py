from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models.employee import User
from models.attendance import AttendanceLog
from core.logging_config import get_logger

logger = get_logger(__name__)


def _parse_default_line(line: str):
    """
    Parsea una línea del formato TXT fijo de SRTime.
    El archivo ya tiene el formato establecido en la tabla att_logs y usuario.
    Formato: identifier(15) + date(DDMMYY,6) + time(HHMM,4) + mark_type(1) + flags(7)
    """
    try:
        if len(line.strip()) < 26:
            return None
        identifier = line[0:15]
        fecha_raw  = line[15:21]
        hora_raw   = line[21:25]
        mark_type  = int(line[25:26])
        flags      = line[26:33] if len(line) >= 33 else ""
        d = datetime.strptime(fecha_raw, "%d%m%y").date()
        t = datetime.strptime(hora_raw, "%H%M").time()
        return identifier, d, t, mark_type, flags
    except Exception:
        return None


def import_att_logs(path, session, progress_signal=None, parser=None):
    logger.info(f"Starting file import: {path}")
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
            # Si hay un parser de addon (import desde TXT de marca), usarlo.
            # Si no, usar el formato fijo default.
            if parser is not None:
                parsed = parser.parse_line(line)
            else:
                parsed = _parse_default_line(line)
            if not parsed:
                # ignored line
                continue
            identifier, date, time, mark_type, flags = parsed
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
    logger.info(f"File import finished: {nuevos} new, {duplicados} duplicates, {total} total")
    return nuevos, duplicados, total, logs_msgs


def import_from_driver(driver_instance, connection_params, session, progress_signal=None):
    nuevos = 0
    duplicados = 0
    total = 0
    logs_msgs = []
    logger.info(f"Starting device import: {driver_instance.display_name}")
    
    try:
        if progress_signal: progress_signal.emit(0, 0, 0, "Conectando al dispositivo...")
        driver_instance.connect(connection_params)
        
        if progress_signal: progress_signal.emit(0, 0, 0, "Descargando registros...")
        
        last_log = {}
        for row in session.query(AttendanceLog.raw_identifier, AttendanceLog.date, AttendanceLog.time).order_by(AttendanceLog.raw_identifier, AttendanceLog.date.desc(), AttendanceLog.time.desc()).all():
            if row.raw_identifier not in last_log:
                last_log[row.raw_identifier] = (row.date, row.time)

        for parsed in driver_instance.get_attendance_logs():
            if not parsed: continue
            total += 1
            identifier, date, time, mark_type, flags = parsed
            
            user = session.query(User).filter_by(identifier=identifier).first()
            if not user:
                user = User(identifier=identifier)
                session.add(user)
                session.commit()
                
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
                    source_file=driver_instance.display_name
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
            if progress_signal and total % 50 == 0:
                progress_signal.emit(total, nuevos, duplicados, msg)
                
    except Exception as e:
        session.rollback()
        logger.error(f"Device import failed: {str(e)}", exc_info=True)
        msg = f"ERROR FATAL: {str(e)}"
        if progress_signal: progress_signal.emit(0, 0, 0, msg)
        logs_msgs.append(msg)
    finally:
        driver_instance.disconnect()
        
    if progress_signal:
        progress_signal.emit(total, nuevos, duplicados, "Completado.")
    
    logger.info(f"Device import finished: {nuevos} new, {duplicados} duplicates, {total} total")
    return nuevos, duplicados, total, logs_msgs