"""Comprobaciones visuales de los indicadores, sin abrir ventanas."""

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QImage, QPainter, QPalette
    from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionButton
    from app.ui.checkbox_style import AccessibleCheckboxStyle
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class CheckboxStyleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.style = AccessibleCheckboxStyle()

    def _render_indicator(self, dark: bool, checked: bool) -> QImage:
        image = QImage(24, 24, QImage.Format.Format_ARGB32)
        image.fill(QColor("#181F28" if dark else "#F8FAFC"))

        option = QStyleOptionButton()
        option.rect = QRect(2, 2, 20, 20)
        option.state = QStyle.StateFlag.State_Enabled
        if checked:
            option.state |= QStyle.StateFlag.State_On
        option.palette = QPalette()
        option.palette.setColor(
            QPalette.ColorRole.Window,
            QColor("#181F28" if dark else "#F8FAFC"),
        )

        painter = QPainter(image)
        self.style.drawPrimitive(
            QStyle.PrimitiveElement.PE_IndicatorCheckBox, option, painter
        )
        painter.end()
        return image

    def test_size_is_20_pixels(self):
        for metric in (
            QStyle.PixelMetric.PM_IndicatorWidth,
            QStyle.PixelMetric.PM_IndicatorHeight,
        ):
            self.assertEqual(self.style.pixelMetric(metric), 20)

    def test_indicator_is_visible_checked_and_unchecked_in_both_themes(self):
        for dark in (False, True):
            with self.subTest(dark=dark):
                unchecked = self._render_indicator(dark, False)
                checked = self._render_indicator(dark, True)

                # El área interna cambia claramente de color al seleccionar.
                self.assertNotEqual(
                    unchecked.pixelColor(11, 6), checked.pixelColor(11, 6)
                )
                # El borde tiene un color diferente al fondo de la ventana.
                self.assertNotEqual(
                    unchecked.pixelColor(3, 11), unchecked.pixelColor(0, 11)
                )
                # La marca blanca se dibuja dentro de la casilla seleccionada.
                mark_color = checked.pixelColor(10, 15)
                self.assertGreater(mark_color.red(), 195)
                self.assertGreater(mark_color.green(), 195)
                self.assertGreater(mark_color.blue(), 195)

    def test_global_style_is_installed_in_main(self):
        main_source = Path("main.py").read_text(encoding="utf-8")
        self.assertIn("from app.ui.checkbox_style import AccessibleCheckboxStyle", main_source)
        self.assertIn("app.setStyle(checkbox_style)", main_source)


if __name__ == "__main__":
    unittest.main()
