"""Framework-level identity names for VCS agent roles."""

from __future__ import annotations

from typing import Final, Literal

KNOWN_ROLES: Final = ("planner", "coder", "reviewer")

IdentityRole = Literal["planner", "coder", "reviewer"]
