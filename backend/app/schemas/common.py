"""Reusable validated field types."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, EmailStr, Field, StringConstraints

_ROLL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9/_-]{1,31}$")


def _normalise_email(value: str) -> str:
    return value.strip().lower()


def _normalise_roll(value: str) -> str:
    value = value.strip().upper()
    if not _ROLL_PATTERN.fullmatch(value):
        raise ValueError("must be 2-32 characters: letters, digits, '/', '_' or '-'")
    return value


Email = Annotated[EmailStr, Field(max_length=254), AfterValidator(_normalise_email)]
RollNumber = Annotated[str, AfterValidator(_normalise_roll)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Department = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Semester = Annotated[int, Field(ge=1, le=12)]
