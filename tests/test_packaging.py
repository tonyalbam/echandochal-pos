import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.database.connection import Database


class PackagingTest(unittest.TestCase):
    def test_frozen_application_stores_data_next_to_executable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "EchandoChalPOS.exe"
            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "executable", str(executable)
            ):
                database = Database()
                try:
                    self.assertEqual(database.app_root, Path(directory))
                    self.assertEqual(
                        database.database_path,
                        Path(directory) / "data" / "echandochal.db",
                    )
                    self.assertTrue(database.database_path.is_file())
                finally:
                    database.close()


if __name__ == "__main__":
    unittest.main()
