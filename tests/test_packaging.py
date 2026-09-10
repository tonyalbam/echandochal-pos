import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.database.connection import Database
from app.database.schema import create_database
from tools.verify_clean_distribution import (
    find_forbidden_entries,
    verify_distribution,
)


class PackagingTest(unittest.TestCase):
    def test_frozen_application_stores_data_next_to_executable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "EchandoChalPOS.exe"
            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "executable", str(executable)
            ):
                database = Database()
                try:
                    create_database(database)
                    self.assertEqual(database.app_root, Path(directory).resolve())
                    self.assertEqual(
                        database.database_path,
                        Path(directory) / "data" / "echandochal.db",
                    )
                    self.assertTrue(database.database_path.is_file())
                    for table in ("productos", "proveedores", "ventas", "compras"):
                        count = database.connection.execute(
                            f"SELECT COUNT(*) FROM {table}"
                        ).fetchone()[0]
                        self.assertEqual(count, 0, table)
                    category_count = database.connection.execute(
                        "SELECT COUNT(*) FROM categorias"
                    ).fetchone()[0]
                    self.assertEqual(category_count, 8)
                finally:
                    database.close()

    def test_distribution_audit_rejects_operational_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            distribution = Path(directory)
            (distribution / "EchandoChalPOS.exe").touch()
            verify_distribution(distribution)

            data_directory = distribution / "data"
            data_directory.mkdir()
            database = data_directory / "echandochal.db"
            database.touch()

            self.assertIn(data_directory, find_forbidden_entries(distribution))
            self.assertIn(database, find_forbidden_entries(distribution))
            with self.assertRaises(ValueError):
                verify_distribution(distribution)

    def test_pyinstaller_spec_only_packages_static_resources(self) -> None:
        spec = Path("echandochal_pos.spec").read_text(encoding="utf-8")

        self.assertIn('datas = [("app/assets", "app/assets")]', spec)
        self.assertNotIn('(\"data\", \"data\")', spec)
        self.assertNotIn('(\"backups\", \"backups\")', spec)

    def test_operational_databases_are_ignored_by_git(self) -> None:
        ignore_rules = Path(".gitignore").read_text(encoding="utf-8")

        self.assertIn("data/", ignore_rules)
        self.assertIn("*.db", ignore_rules)
        self.assertIn("*.db-wal", ignore_rules)
        self.assertIn("*.db-shm", ignore_rules)


if __name__ == "__main__":
    unittest.main()
