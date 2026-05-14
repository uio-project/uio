"""Framework-level identity names for VCS agent roles."""

from __future__ import annotations

from typing import Final, Literal

__all__ = ["KNOWN_ROLES", "IdentityRole"]

KNOWN_ROLES: Final = ("planner", "coder", "reviewer", "closer")

IdentityRole = Literal["planner", "coder", "reviewer", "closer"]
