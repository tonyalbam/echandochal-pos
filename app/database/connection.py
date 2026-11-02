from pathlib import Path
import sqlite3

from app.database.data_location import installation_directory, resolve_existing_database


class Database:
    """Conexión a una base existente. Nunca crea una base vacía por accidente."""

    def __init__(self) -> None:
        self.app_root = installation_directory()
        self.database_path = resolve_existing_database()
        self.data_directory = self.database_path.parent

        # SQLite mode=rw rechaza archivos inexistentes; no crea bases vacías.
        uri = self.database_path.resolve().as_uri() + "?mode=rw"
        self.connection = sqlite3.connect(uri, uri=True)
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
