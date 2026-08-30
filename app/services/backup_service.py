from pathlib import Path
import sqlite3

from app.database.connection import Database


class BackupService:
    """Crea respaldos consistentes de la base de datos SQLite."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create_backup(self, destination: str | Path) -> Path:
        output_path = Path(destination)

        if output_path.suffix.lower() != ".db":
            output_path = output_path.with_suffix(".db")

        source_path = getattr(self.database, "database_path", None)
        if source_path is not None:
            if output_path.resolve() == Path(source_path).resolve():
                raise ValueError(
                    "El respaldo no puede reemplazar la base de datos activa."
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        target_connection = sqlite3.connect(output_path)
        try:
            self.database.connection.backup(target_connection)
            integrity = target_connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            if str(integrity).lower() != "ok":
                raise RuntimeError(
                    "La validación de integridad del respaldo falló."
                )
        finally:
            target_connection.close()

        return output_path
