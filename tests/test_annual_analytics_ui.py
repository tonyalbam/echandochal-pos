"""Prueba rápida del render del panel anual en Qt sin base de producción."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from app.ui.annual_analytics_panel import AnnualAnalyticsPanel


class AnnualAnalyticsUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_renders_both_themes_and_empty_charts(self):
        panel = AnnualAnalyticsPanel()
        data = {
            "year": 2026,
            "marca_mas_vendida": None,
            "producto_mas_vendido": None,
            "producto_mas_rentable": None,
            "producto_menos_vendido": None,
            "utilidad_acumulada": [
                {"mes": month, "utilidad": 0.0, "acumulada": 0.0}
                for month in range(1, 13)
            ],
            "top_productos_ingresos": [],
            "sin_venta_90_dias": [],
        }
        panel.set_data(data)
        self.assertEqual(panel.stagnant.rowCount(), 0)
        self.assertEqual(panel.pie_chart.chart().series()[0].count(), 0)
        panel.apply_theme(True)
        panel.apply_theme(False)
        self.assertEqual(panel.period.text(), "Indicadores acumulados del año 2026")
        panel.close()


if __name__ == "__main__":
    unittest.main()
