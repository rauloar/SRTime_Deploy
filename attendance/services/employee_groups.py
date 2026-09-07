from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.employee import SHIFT_ASSIGNMENT_GROUP, SHIFT_ASSIGNMENT_MANUAL, User
from models.employee_group import EmployeeGroup

@dataclass(frozen=True)
class GroupAssignmentResult:
    assigned: int
    shift_updated: int
    manual_preserved: int
    missing_users: list[int]


def list_groups(session: Session) -> list[dict]:
    counts = dict(
        session.query(User.group_id, func.count(User.id))
        .filter(User.group_id.isnot(None))
        .group_by(User.group_id)
        .all()
    )
    groups = session.query(EmployeeGroup).order_by(EmployeeGroup.name.asc()).all()
    return [
        {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "shift_id": group.shift_id,
            "is_active": group.is_active,
            "employee_count": int(counts.get(group.id, 0)),
        }
        for group in groups
    ]


def create_group(
    session: Session,
    *,
    name: str,
    description: str | None = None,
    shift_id: int | None = None,
    is_active: bool = True,
) -> EmployeeGroup:
    group = EmployeeGroup(
        name=name.strip(),
        description=(description or "").strip() or None,
        shift_id=shift_id,
        is_active=is_active,
    )
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


def update_group(
    session: Session,
    group: EmployeeGroup,
    *,
    name: str | None = None,
    description: str | None = None,
    update_description: bool = False,
    shift_id: int | None = None,
    update_shift: bool = False,
    is_active: bool | None = None,
) -> EmployeeGroup:
    if name is not None:
        group.name = name.strip()
    if update_description:
        group.description = (description or "").strip() or None
    if update_shift:
        group.shift_id = shift_id
    if is_active is not None:
        group.is_active = is_active
    session.commit()
    session.refresh(group)
    return group


def assign_users_to_group(
    session: Session,
    *,
    group: EmployeeGroup,
    user_ids: list[int],
    override_manual: bool = False,
) -> GroupAssignmentResult:
    unique_ids = sorted({int(user_id) for user_id in user_ids})
    users = session.query(User).filter(User.id.in_(unique_ids)).all() if unique_ids else []
    found_ids = {int(user.id) for user in users}

    assigned = 0
    shift_updated = 0
    manual_preserved = 0

    for employee in users:
        if employee.group_id != group.id:
            employee.group_id = group.id
            assigned += 1

        should_update_shift = (
            group.shift_id is not None
            and (
                override_manual
                or employee.shift_id is None
                or employee.shift_assignment_source == SHIFT_ASSIGNMENT_GROUP
            )
        )
        if should_update_shift:
            if employee.shift_id != group.shift_id:
                employee.shift_id = group.shift_id
                shift_updated += 1
            employee.shift_assignment_source = SHIFT_ASSIGNMENT_GROUP
        elif employee.shift_assignment_source == SHIFT_ASSIGNMENT_MANUAL and employee.shift_id != group.shift_id:
            manual_preserved += 1

    session.commit()
    return GroupAssignmentResult(
        assigned=assigned,
        shift_updated=shift_updated,
        manual_preserved=manual_preserved,
        missing_users=[user_id for user_id in unique_ids if user_id not in found_ids],
    )


def apply_group_shift(
    session: Session,
    *,
    group: EmployeeGroup,
    include_manual: bool = False,
) -> GroupAssignmentResult:
    if group.shift_id is None:
        return GroupAssignmentResult(assigned=0, shift_updated=0, manual_preserved=0, missing_users=[])

    users = session.query(User).filter(User.group_id == group.id).all()
    shift_updated = 0
    manual_preserved = 0

    for employee in users:
        is_manual = employee.shift_assignment_source == SHIFT_ASSIGNMENT_MANUAL
        if is_manual and not include_manual:
            manual_preserved += 1
            continue
        if employee.shift_id != group.shift_id:
            employee.shift_id = group.shift_id
            shift_updated += 1
        employee.shift_assignment_source = SHIFT_ASSIGNMENT_GROUP

    session.commit()
    return GroupAssignmentResult(
        assigned=0,
        shift_updated=shift_updated,
        manual_preserved=manual_preserved,
        missing_users=[],
    )
