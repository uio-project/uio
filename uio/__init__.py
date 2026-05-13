"""uio — provider-agnostic AI agent/skill/prompt runner."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("uio-ai")
except PackageNotFoundError:
    __version__ = "unknown"
