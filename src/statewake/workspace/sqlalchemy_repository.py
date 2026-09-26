"""Optional SQLAlchemy-backed StateWake workspace repository."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .sqlite_repository import SqliteWorkspaceRepository


class SqlAlchemyWorkspaceRepository(SqliteWorkspaceRepository):
    """Expose the stable repository contract through a SQLAlchemy engine."""

    def __init__(self, path: Path) -> None:
        """Initialize a SQLAlchemy-backed repository for a SQLite database path."""
        try:
            from sqlalchemy import create_engine
        except ImportError as exc:
            raise RuntimeError(
                "SQLAlchemy backend requires the optional 'sqlalchemy' package."
            ) from exc

        super().__init__(path)
        self._engine: Any = create_engine(
            f"sqlite:///{path.resolve()}",
            connect_args={"timeout": 30.0},
        )

    def connect(self) -> Any:
        """Return a pooled DB-API connection managed by SQLAlchemy."""
        connection = self._engine.raw_connection()
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def dispose(self) -> None:
        """Release SQLAlchemy connection-pool resources."""
        self._engine.dispose()


__all__ = ["SqlAlchemyWorkspaceRepository"]
