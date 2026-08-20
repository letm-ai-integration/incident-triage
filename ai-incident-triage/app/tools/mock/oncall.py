"""
Mock on-call/support contact lookup. Reads a single current on-call
record from a plain-text file. Replace with a real on-call system
integration (PagerDuty, Opsgenie, etc.) later.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ONCALL_FILE_PATH = Path("data/oncall/current_oncall.txt")


@dataclass(frozen=True)
class OnCallContact:
    name: str
    role: str
    email: str
    team: str
    status: str


def get_current_oncall() -> OnCallContact:
    if not ONCALL_FILE_PATH.exists():
        raise FileNotFoundError(f"On-call mock data file not found: {ONCALL_FILE_PATH}")

    fields = {}
    for line in ONCALL_FILE_PATH.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()

    return OnCallContact(
        name=fields["name"],
        role=fields["role"],
        email=fields["email"],
        team=fields["team"],
        status=fields["status"],
    )