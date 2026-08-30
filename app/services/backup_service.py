from pathlib import Path
import sqlite3
from datetime import datetime

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

    def validate_backup(self, source: str | Path) -> dict:
        """Valida integridad y estructura mínima de un respaldo."""

        source_path = Path(source)
        if not source_path.is_file():
            raise ValueError("El archivo de respaldo no existe.")

        active_path = getattr(self.database, "database_path", None)
        if active_path is not None:
            if source_path.resolve() == Path(active_path).resolve():
                raise ValueError(
                    "No se puede restaurar desde la base de datos activa."
                )

        required_tables = {
            "configuracion",
            "productos",
            "ventas",
            "detalle_venta",
            "compras",
            "detalle_compra",
        }

        try:
            connection = sqlite3.connect(
                f"file:{source_path.resolve()}?mode=ro",
                uri=True,
            )
        except sqlite3.Error as error:
            raise ValueError(
                "No fue posible abrir el archivo como base SQLite."
            ) from error

        try:
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            if str(integrity).lower() != "ok":
                raise ValueError(
                    "El archivo no superó la validación de integridad."
                )

            tables = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }
            missing = required_tables - tables
            if missing:
                raise ValueError(
                    "El archivo no es un respaldo completo de Echando Chal POS."
                )

            counts = {
                "productos": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM productos"
                    ).fetchone()[0]
                ),
                "ventas": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM ventas"
                    ).fetchone()[0]
                ),
                "compras": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM compras"
                    ).fetchone()[0]
                ),
            }
        except sqlite3.Error as error:
            raise ValueError(
                "El archivo no contiene una base de datos válida."
            ) from error
        finally:
            connection.close()

        return {
            "path": source_path,
            "productos": counts["productos"],
            "ventas": counts["ventas"],
            "compras": counts["compras"],
        }

    def restore_backup(
        self,
        source: str | Path,
        safety_directory: str | Path | None = None,
    ) -> dict:
        """Restaura un respaldo y conserva una copia previa automática."""

        backup_info = self.validate_backup(source)
        source_path = Path(source)

        if safety_directory is None:
            app_root = getattr(self.database, "app_root", None)
            if app_root is None:
                safety_directory = source_path.parent
            else:
                safety_directory = Path(app_root) / "backups"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safety_path = Path(safety_directory) / (
            f"antes_de_restaurar_{timestamp}.db"
        )
        self.create_backup(safety_path)

        try:
            source_connection = sqlite3.connect(
                f"file:{source_path.resolve()}?mode=ro",
                uri=True,
            )
            try:
                self.database.commit()
                source_connection.backup(self.database.connection)
                self.database.commit()
            finally:
                source_connection.close()

            integrity = self.database.connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            foreign_key_errors = self.database.connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            if str(integrity).lower() != "ok" or foreign_key_errors:
                raise RuntimeError(
                    "La base restaurada no superó la validación final."
                )
        except Exception as error:
            rollback_connection = sqlite3.connect(
                f"file:{safety_path.resolve()}?mode=ro",
                uri=True,
            )
            try:
                rollback_connection.backup(self.database.connection)
                self.database.commit()
            finally:
                rollback_connection.close()

            raise RuntimeError(
                "La restauración falló; se recuperó el estado anterior."
            ) from error

        return {
            **backup_info,
            "safety_backup": safety_path,
        }
