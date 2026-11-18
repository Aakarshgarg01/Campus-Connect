"""Admin command line. Faculty and admin accounts cannot self-register; create them here.

Usage (from backend/, venv active):
    python -m app.cli create-user --role faculty --name "Dr. A. Rao" --email rao@college.edu \
        --employee-id FAC1024 --department "Computer Science"
The password is prompted for (hidden). For non-interactive use (CI, deploy), set NEW_USER_PASSWORD.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import or_, select

from app.core.security import hash_password
from app.database.connection import get_session_factory
from app.models import User, UserRole
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="Create a faculty or admin account")
    create.add_argument("--role", choices=[UserRole.FACULTY.value, UserRole.ADMIN.value], required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--employee-id", required=True)
    create.add_argument("--department")
    args = parser.parse_args(argv)
    if args.command == "create-user":
        create_user(args)


if __name__ == "__main__":
    main()
