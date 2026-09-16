"""Interface desktop do BR-MANGUE sobre o núcleo científico independente."""

__all__ = ["main"]


def main() -> None:
    from .app import main as _main

    _main()

