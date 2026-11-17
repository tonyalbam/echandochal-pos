"""Marca, maximización y versión coordinada de Echando Chal POS."""

import ast
import os
from pathlib import Path
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.database.schema import create_database
from app.ui.main_window import MainWindow
from app.version import APP_VERSION
from tools.create_app_icon import build_icon


ROOT = Path(__file__).resolve().parents[1]
ICON_PNG = ROOT / "app" / "assets" / "echandochal_icon.png"


class MemoryDB:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
    def cursor(self):
        return self.connection.cursor()
    def commit(self):
        self.connection.commit()
    def rollback(self):
        self.connection.rollback()
    def close(self):
        self.connection.close()


class AppBrandingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_icon_is_real_transparent_png_and_loads_in_qt(self):
        self.assertTrue(ICON_PNG.is_file())
        with Image.open(ICON_PNG) as logo:
            self.assertEqual(logo.format, "PNG")
            self.assertIn(logo.mode, ("RGBA", "P"))
            alpha = logo.convert("RGBA").getchannel("A")
            self.assertLess(alpha.getextrema()[0], 255)
            self.assertGreaterEqual(logo.width, 128)
            self.assertEqual(logo.size[0], logo.size[1])
        icon = QIcon(str(ICON_PNG))
        self.assertFalse(icon.isNull())
        self.assertFalse(icon.pixmap(32, 32).isNull())

    def test_windows_ico_contains_multiple_sizes_and_alpha(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            icon_path = Path(tmp) / "test.ico"
            self.assertEqual(build_icon(ICON_PNG, icon_path), icon_path)
            with Image.open(icon_path) as icon:
                self.assertEqual(icon.format, "ICO")
                self.assertIn((16, 16), icon.info["sizes"])
                self.assertIn((32, 32), icon.info["sizes"])
                self.assertIn((256, 256), icon.info["sizes"])

    def test_main_window_displays_version_1_2_0_in_footer(self):
        database = MemoryDB()
        create_database(database)
        window = MainWindow(database)
        try:
            self.assertEqual(APP_VERSION, "1.2.0")
            self.assertEqual(
                window.version_label.text(),
                f"Echando Chal POS\\nv{APP_VERSION}".replace("\\n", "\n"),
            )
            self.assertIn(APP_VERSION, window.version_label.text())
        finally:
            window.close()
            database.close()

    def test_startup_uses_window_maximize_not_borderless_fullscreen(self):
        tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
        calls = [
            n.func.attr for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "window"
        ]
        self.assertIn("showMaximized", calls)
        self.assertNotIn("showFullScreen", calls)
        self.assertNotIn("show", calls)

    def test_build_and_installer_use_same_version_and_embed_icon(self):
        script = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("app\\version.py", script)
        self.assertIn('tools\\create_app_icon.py', script)
        self.assertIn('$Version -ne $SourceVersion', script)
        spec = (ROOT / "echandochal_pos.spec").read_text(encoding="utf-8")
        self.assertIn('icon="app/assets/echandochal_icon.ico"', spec)
        self.assertIn('datas = [("app/assets", "app/assets")]', spec)
        setup = (ROOT / "installer/echandochal_pos.iss").read_text(
            encoding="utf-8"
        )
        self.assertIn("SetupIconFile=", setup)
        self.assertIn('#define MyAppVersion "1.2.0"', setup)
        workflow = (ROOT / ".github/workflows/build-windows.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("default: 1.2.0", workflow)


if __name__ == "__main__":
    unittest.main()
