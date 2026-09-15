"""Public command-line entry point for StateWake."""


def main() -> None:
    """Execute the StateWake command-line interface."""
    from .main import main as run_cli

    run_cli()


__all__ = ["main"]
