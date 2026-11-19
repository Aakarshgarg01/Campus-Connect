"""Admin command line. Faculty and admin accounts cannot self-register; create them here.

Usage (from backend/, venv active):
    python -m app.cli create-user --role faculty --name "Dr. A. Rao" --email rao@college.edu \
        --employee-id FAC1024 --department "Computer Science"
The password is prompted for (hidden). For non-interactive use (CI, deploy), set NEW_USER_PASSWORD.

Local testing only:  python -m app.cli seed-demo   (default logins; refused when ENVIRONMENT=production)
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import or_, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.database.connection import get_session_factory
from app.models import Student, User, UserRole
from app.schemas.common import Department, Email, Name
from app.schemas.user_schema import Password


def _validate(adapter_type, value, label):
    try:
        return TypeAdapter(adapter_type).validate_python(value)
    except ValidationError as exc:
        sys.exit(f"Invalid {label}: {exc.errors()[0]['msg']}")


def create_user(args: argparse.Namespace) -> None:
    role = UserRole(args.role)
    name = _validate(Name, args.name, "name")
    email = _validate(Email, args.email, "email")
    department = _validate(Department, args.department, "department") if args.department else None
    employee_id = args.employee_id.strip().upper()
    password = os.environ.get("NEW_USER_PASSWORD") or getpass.getpass("Password: ")
    if not os.environ.get("NEW_USER_PASSWORD") and getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")
    password = _validate(Password, password, "password")

    with get_session_factory()() as db:
        existing = db.scalar(select(User).where(or_(User.email == email, User.employee_id == employee_id)))
        if existing:
            sys.exit("A user with this email or employee ID already exists.")
        user = User(name=name, email=email, employee_id=employee_id, department=department,
                    role=role, hashed_password=hash_password(password))
        db.add(user)
        db.commit()
        print(f"Created {role.value} user id={user.id} email={email} employee_id={employee_id}")


# Default local/testing logins. Development only: seed-demo refuses to run in production.
DEMO_PASSWORD = "Campus@123"
DEMO_FACULTY = {"name": "Demo Faculty", "email": "demo.faculty@example.com", "employee_id": "FAC1024"}
DEMO_STUDENT = {"name": "Demo Student", "email": "demo.student@example.com", "roll_number": "CS21041",
                "department": "Computer Science", "semester": 7}


def seed_demo() -> None:
    """Create (or reset the password of) the default testing logins. Idempotent."""
    if get_settings().environment == "production":
        sys.exit("Refusing to create demo accounts in production.")
    hashed = hash_password(DEMO_PASSWORD)
    with get_session_factory()() as db:
        faculty = db.scalar(select(User).where(User.employee_id == DEMO_FACULTY["employee_id"]))
        if faculty is None:
            faculty = User(name=DEMO_FACULTY["name"], email=DEMO_FACULTY["email"], role=UserRole.FACULTY,
                           employee_id=DEMO_FACULTY["employee_id"], department=DEMO_STUDENT["department"],
                           hashed_password=hashed)
            db.add(faculty)
        else:
            faculty.hashed_password, faculty.is_active = hashed, True

        student = db.scalar(select(Student).where(Student.roll_number == DEMO_STUDENT["roll_number"]))
        if student is None:
            student = Student(**{k: DEMO_STUDENT[k] for k in ("name", "email", "roll_number", "department", "semester")})
            db.add(student)
        account = student.user or db.scalar(select(User).where(User.email == DEMO_STUDENT["email"]))
        if account is None:
            account = User(name=DEMO_STUDENT["name"], email=DEMO_STUDENT["email"], role=UserRole.STUDENT,
                           department=DEMO_STUDENT["department"], hashed_password=hashed)
        else:
            account.hashed_password, account.is_active = hashed, True
        student.user = account
        db.commit()
    print(f"Demo logins ready (development only). Password for both: {DEMO_PASSWORD}\n"
          f"  Faculty: {DEMO_FACULTY['employee_id']} or {DEMO_FACULTY['email']}\n"
          f"  Student: {DEMO_STUDENT['roll_number']} or {DEMO_STUDENT['email']}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed-demo", help="Create/reset default testing logins (refused in production)")
    create = commands.add_parser("create-user", help="Create a faculty or admin account")
    create.add_argument("--role", choices=[UserRole.FACULTY.value, UserRole.ADMIN.value], required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--employee-id", required=True)
    create.add_argument("--department")
    args = parser.parse_args(argv)
    if args.command == "create-user":
        create_user(args)
    elif args.command == "seed-demo":
        seed_demo()


if __name__ == "__main__":
    main()
