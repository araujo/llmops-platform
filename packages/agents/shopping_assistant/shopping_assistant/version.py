"""Package version helper (avoids import cycles with ``plugin``)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as pkg_version


def get_package_version() -> str:
    try:
        return pkg_version("shopping-assistant")
    except PackageNotFoundError:
        return "0.0.0"
