from datetime import time

from models.employee import SHIFT_ASSIGNMENT_GROUP, SHIFT_ASSIGNMENT_MANUAL, User
from models.employee_group import EmployeeGroup
from models.shift import Shift
from services.employee_groups import apply_group_shift, assign_users_to_group, create_group


def test_group_assignment_is_idempotent_and_preserves_manual_shift(test_db):
    factory = Shift(name="Fábrica", expected_in=time(8, 0), expected_out=time(16, 0))
    admin = Shift(name="Administración", expected_in=time(9, 0), expected_out=time(14, 0))
    test_db.add_all([factory, admin])
    test_db.commit()

    group = create_group(test_db, name="Fábrica", shift_id=factory.id)
    manual_employee = User(
        identifier="000000000001001",
        first_name="Manual",
        shift_id=admin.id,
        shift_assignment_source=SHIFT_ASSIGNMENT_MANUAL,
    )
    no_shift_employee = User(
        identifier="000000000001002",
        first_name="Sin turno",
        shift_id=None,
        shift_assignment_source=SHIFT_ASSIGNMENT_MANUAL,
    )
    test_db.add_all([manual_employee, no_shift_employee])
    test_db.commit()

    first = assign_users_to_group(
        test_db,
        group=group,
        user_ids=[manual_employee.id, no_shift_employee.id],
        override_manual=False,
    )
    second = assign_users_to_group(
        test_db,
        group=group,
        user_ids=[manual_employee.id, no_shift_employee.id],
        override_manual=False,
    )

    test_db.refresh(manual_employee)
    test_db.refresh(no_shift_employee)
    assert first.assigned == 2
    assert first.shift_updated == 1
    assert first.manual_preserved == 1
    assert second.assigned == 0
    assert second.shift_updated == 0
    assert second.manual_preserved == 1
    assert manual_employee.shift_id == admin.id
    assert manual_employee.shift_assignment_source == SHIFT_ASSIGNMENT_MANUAL
    assert no_shift_employee.shift_id == factory.id
    assert no_shift_employee.shift_assignment_source == SHIFT_ASSIGNMENT_GROUP


def test_group_shift_can_override_manual_assignments(test_db):
    old_shift = Shift(name="Viejo", expected_in=time(6, 0), expected_out=time(14, 0))
    new_shift = Shift(name="Nuevo", expected_in=time(14, 0), expected_out=time(22, 0))
    test_db.add_all([old_shift, new_shift])
    test_db.commit()

    group = EmployeeGroup(name="Tarde", shift_id=new_shift.id)
    employee = User(
        identifier="000000000001003",
        first_name="Operario",
        shift_id=old_shift.id,
        shift_assignment_source=SHIFT_ASSIGNMENT_MANUAL,
        group_id=None,
    )
    test_db.add_all([group, employee])
    test_db.commit()

    result = assign_users_to_group(
        test_db,
        group=group,
        user_ids=[employee.id],
        override_manual=True,
    )
    apply_result = apply_group_shift(test_db, group=group, include_manual=True)

    test_db.refresh(employee)
    assert result.assigned == 1
    assert result.shift_updated == 1
    assert apply_result.shift_updated == 0
    assert employee.group_id == group.id
    assert employee.shift_id == new_shift.id
    assert employee.shift_assignment_source == SHIFT_ASSIGNMENT_GROUP
