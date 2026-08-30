import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.database.schema import create_database
from app.services.backup_service import BackupService


class MemoryDatabase:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def cursor(self) -> sqlite3.Cursor:
        return self.connection.cursor()

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


class RestoreServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.active_database = MemoryDatabase()
        create_database(self.active_database)
        self._insert_product(
            self.active_database,
            "ACTUAL",
            "Producto actual",
        )

    def tearDown(self) -> None:
        self.active_database.close()

    @staticmethod
    def _insert_product(
        database: MemoryDatabase,
        code: str,
        name: str,
    ) -> None:
        cursor = database.cursor()
        cursor.execute(
            """
            INSERT INTO productos (
                codigo, nombre, costo, precio, existencia
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (code, name, 10, 20, 5),
        )
        database.commit()

    def test_restore_replaces_data_and_preserves_previous_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backup_database = MemoryDatabase()
            create_database(backup_database)
            self._insert_product(
                backup_database,
                "RESPALDO",
                "Producto del respaldo",
            )
            source_path = BackupService(backup_database).create_backup(
                Path(directory) / "origen.db"
            )
            backup_database.close()

            result = BackupService(
                self.active_database
            ).restore_backup(
                source_path,
                safety_directory=directory,
            )

            active_codes = [
                row[0]
                for row in self.active_database.connection.execute(
                    "SELECT codigo FROM productos ORDER BY codigo"
                ).fetchall()
            ]
            self.assertEqual(active_codes, ["RESPALDO"])
            self.assertEqual(result["productos"], 1)
            self.assertTrue(result["safety_backup"].exists())

            safety_connection = sqlite3.connect(result["safety_backup"])
            try:
                safety_codes = [
                    row[0]
                    for row in safety_connection.execute(
                        "SELECT codigo FROM productos"
                    ).fetchall()
                ]
            finally:
                safety_connection.close()

            self.assertEqual(safety_codes, ["ACTUAL"])

    def test_incomplete_database_is_rejected_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid_path = Path(directory) / "incompleta.db"
            invalid_connection = sqlite3.connect(invalid_path)
            invalid_connection.execute("CREATE TABLE ejemplo (id INTEGER)")
            invalid_connection.close()

            with self.assertRaises(ValueError):
                BackupService(self.active_database).restore_backup(
                    invalid_path,
                    safety_directory=directory,
                )

            current_code = self.active_database.connection.execute(
                "SELECT codigo FROM productos"
            ).fetchone()[0]
            self.assertEqual(current_code, "ACTUAL")


if __name__ == "__main__":
    unittest.main()
