import sqlite3
import tempfile
import unittest
from datetime import datetime
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


class BackupServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MemoryDatabase()
        create_database(self.database)
        cursor = self.database.cursor()
        cursor.execute(
            """
            INSERT INTO productos (
                codigo, nombre, costo, precio, existencia
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("P-RESPALDO", "Producto respaldado", 10, 20, 5),
        )
        self.database.commit()

    def tearDown(self) -> None:
        self.database.close()

    def test_backup_is_valid_and_contains_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = BackupService(self.database).create_backup(
                Path(directory) / "respaldo"
            )

            self.assertEqual(output_path.suffix, ".db")
            self.assertTrue(output_path.exists())

            restored = sqlite3.connect(output_path)
            try:
                integrity = restored.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]
                product = restored.execute(
                    "SELECT codigo, nombre FROM productos"
                ).fetchone()
            finally:
                restored.close()

            self.assertEqual(integrity, "ok")
            self.assertEqual(product[0], "P-RESPALDO")
            self.assertEqual(product[1], "Producto respaldado")

    def test_backup_cannot_replace_active_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            active_path = Path(directory) / "active.db"
            self.database.database_path = active_path

            with self.assertRaises(ValueError):
                BackupService(self.database).create_backup(active_path)

    def test_automatic_backup_is_created_only_once_per_day(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = BackupService(self.database)
            moment = datetime(2026, 8, 30, 9, 15)

            first = service.create_daily_automatic_backup(directory, moment)
            second = service.create_daily_automatic_backup(directory, moment)

            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(first["path"], second["path"])
            self.assertEqual(
                first["path"].name,
                "echandochal_automatico_20260830.db",
            )
            self.assertEqual(len(list(Path(directory).glob("*.db"))), 1)
            info = service.validate_backup(first["path"])
            self.assertEqual(info["productos"], 1)


if __name__ == "__main__":
    unittest.main()
