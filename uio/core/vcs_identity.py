"""Abstract interface that VCS identity providers must satisfy."""

from __future__ import annotations

from typing import Protocol


class VcsIdentityProvider(Protocol):
    """Protocol that every VCS identity provider must implement.

    Each provider handles credential acquisition, commit author metadata,
    and attribution instructions for its platform.
    """

    def get_token(self, role: str) -> str:
        """Return a short-lived credential token for the given role."""
        ...

    def known_roles(self) -> tuple[str, ...]:
        """Return the set of valid identity role names for this provider."""
        ...

    def commit_author(self, role: str) -> dict[str, str]:
        """Return git author metadata (name and email) for the given role."""
        ...

    def attribution_instructions(self, role: str) -> str:
        """Return system-prompt attribution instructions for the given role."""
        ...
