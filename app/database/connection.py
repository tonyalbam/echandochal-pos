from pathlib import Path
import sqlite3
import sys


class Database:
    """Gestiona la conexión SQLite de Echando Chal POS."""

    def __init__(self) -> None:
        if getattr(sys, "frozen", False):
            self.app_root = Path(sys.executable).resolve().parent
        else:
            self.app_root = Path(__file__).resolve().parents[2]

        self.data_directory = self.app_root / "data"
        self.data_directory.mkdir(parents=True, exist_ok=True)

        self.database_path = self.data_directory / "echandochal.db"

        self.connection = sqlite3.connect(self.database_path)

        self.connection.row_factory = sqlite3.Row

        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA busy_timeout = 5000")

    def cursor(self) -> sqlite3.Cursor:
        return self.connection.cursor()

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        if self.connection:
            self.connection.close()
