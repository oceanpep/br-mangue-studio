"""Interface desktop do BR-MANGUE sobre o núcleo científico independente."""

from .geospatial_runtime import configure_geospatial_runtime

configure_geospatial_runtime()

__all__ = ["main"]


def main() -> None:
    from .app import main as _main

    _main()
