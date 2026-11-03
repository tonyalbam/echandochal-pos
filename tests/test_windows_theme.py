"""Comprueba la selección automática y el cambio en vivo de tema de Windows."""
import os
import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from app.ui import theme


class WindowsThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_windows_registry_prefers_apps_theme(self):
        key = MagicMock()
        fake_registry = SimpleNamespace(
            HKEY_CURRENT_USER=1,
            OpenKey=lambda *_: key,
            QueryValueEx=lambda *_: (0, 4),
        )
        with patch.object(theme.sys, "platform", "win32"), patch.dict(
            "sys.modules", {"winreg": fake_registry}
        ):
            self.assertTrue(theme.windows_uses_dark_mode())
            fake_registry.QueryValueEx = lambda *_: (1, 4)
            self.assertFalse(theme.windows_uses_dark_mode())

    def test_theme_colors_are_readable_and_different(self):
        dark = theme.theme_colors(True)
        light = theme.theme_colors(False)
        self.assertNotEqual(dark["window"], light["window"])
        self.assertNotEqual(dark["text"], light["text"])
        self.assertEqual(dark["card_text"], "#FFFFFF")
        self.assertEqual(light["card_text"], "#FFFFFF")
        self.assertIn(dark["text"], theme.build_stylesheet(dark))
        self.assertIn(light["text"], theme.build_stylesheet(light))

    def test_theme_changes_while_application_is_running(self):
        changes = []
        with patch.object(theme, "windows_uses_dark_mode", return_value=True) as mocked:
            manager = theme.WindowsThemeManager(self.app)
            try:
                manager.theme_changed.connect(changes.append)
                self.assertTrue(manager.dark_mode)
                self.assertEqual(
                    self.app.palette().color(QPalette.ColorRole.Window).name().upper(),
                    theme.theme_colors(True)["window"].upper(),
                )
                mocked.return_value = False
                manager.refresh()
                self.assertFalse(manager.dark_mode)
                self.assertEqual(changes, [False])
                self.assertEqual(
                    self.app.palette().color(QPalette.ColorRole.Window).name().upper(),
                    theme.theme_colors(False)["window"].upper(),
                )
                manager.refresh()
                self.assertEqual(changes, [False])
            finally:
                manager.timer.stop()
                self.app.setStyleSheet("")

    def test_uses_system_palette_if_registry_is_unavailable(self):
        with patch.object(theme, "windows_uses_dark_mode", return_value=None):
            self.assertIsInstance(theme.detect_dark_mode(self.app), bool)


if __name__ == "__main__":
    unittest.main()
