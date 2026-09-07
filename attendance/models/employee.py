from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, String
from core.database import Base


TERMINAL_PRIVILEGE_USER = 0
TERMINAL_PRIVILEGE_ADMIN = 14
TERMINAL_PRIVILEGES = (TERMINAL_PRIVILEGE_USER, TERMINAL_PRIVILEGE_ADMIN)

SHIFT_ASSIGNMENT_MANUAL = "MANUAL"
SHIFT_ASSIGNMENT_GROUP = "GROUP"
SHIFT_ASSIGNMENT_SOURCES = (SHIFT_ASSIGNMENT_MANUAL, SHIFT_ASSIGNMENT_GROUP)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "terminal_privilege IN (0, 14)",
            name="ck_users_terminal_privilege_valid",
        ),
        CheckConstraint(
            "shift_assignment_source IN ('MANUAL', 'GROUP')",
            name="ck_users_shift_assignment_source_valid",
        ),
    )

    id = Column(Integer, primary_key=True)
    identifier = Column(String(15), unique=True, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    is_active = Column(Boolean, default=True)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("employee_group.id"), nullable=True)
    shift_assignment_source = Column(String(20), nullable=False, default=SHIFT_ASSIGNMENT_MANUAL)
    # Privilegio del empleado dentro de la terminal biométrica, no dentro de SRTime.
    # ZKTeco usa 0 = USER y 14 = ADMIN. Sundial/TM-MR001 no trae este dato, por
    # lo que conserva el default USER para no alterar el contrato del importer.
    terminal_privilege = Column(Integer, nullable=False, default=TERMINAL_PRIVILEGE_USER)
