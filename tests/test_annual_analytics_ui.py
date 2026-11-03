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
        self.assertEqual(panel.pie_chart.products, [])
        panel.apply_theme(True)
        panel.apply_theme(False)
        self.assertEqual(panel.period.text(), "Indicadores acumulados del año 2026")
        panel.show()
        self.app.processEvents()
        panel.performance_chart.repaint()
        panel.pie_chart.repaint()
        self.app.processEvents()
        self.assertEqual(len(panel.performance_chart.months), 12)
        panel.close()

    def test_all_future_months_render_without_crashing(self):
        panel = AnnualAnalyticsPanel()
        panel.performance_chart.set_data([
            {"mes": month, "utilidad": None, "acumulada": None}
            for month in range(1, 13)
        ])
        panel.show()
        self.app.processEvents()
        panel.performance_chart.repaint()
        panel.apply_theme(True)
        self.app.processEvents()
        panel.performance_chart.repaint()
        panel.close()

    def test_populated_charts_render_in_both_themes(self):
        panel = AnnualAnalyticsPanel()
        data = {
            "year": 2026,
            "marca_mas_vendida": {"nombre": "Lanas", "unidades": 10},
            "producto_mas_vendido": {
                "nombre": "Lana azul", "unidades": 10, "categoria": "Algodón",
            },
            "producto_mas_rentable": {"nombre": "Lana azul", "utilidad": 225},
            "producto_menos_vendido": {
                "nombre": "Ovillo verde", "unidades": 0, "dias": 180,
            },
            "utilidad_acumulada": [
                {"mes": month,
                 "utilidad": (0 if month <= 11 else None),
                 "acumulada": ((month * 50 if month < 6 else -month * 15)
                                if month <= 11 else None)}
                for month in range(1, 13)
            ],
            "top_productos_ingresos": [
                {"nombre": "Lana azul", "ventas": 250, "porcentaje": 62.5},
                {"nombre": "Ovillo verde", "ventas": 150, "porcentaje": 37.5},
            ],
            "sin_venta_90_dias": [{
                "codigo": "ECH0000001", "nombre": "Ovillo verde",
                "marca": "Marca A", "categoria": "Algodón",
                "existencia": 5, "ultima_venta": None,
                "dias_sin_venta": 180, "costo": 20,
                "precio": 50, "valor_inmovilizado": 100,
            }],
        }
        panel.set_data(data)
        panel.show()
        self.app.processEvents()
        panel.performance_chart.repaint()
        panel.pie_chart.repaint()
        self.assertEqual(len(panel.pie_chart.products), 2)
        self.assertIsNone(panel.performance_chart.months[11]["acumulada"])
        self.assertEqual(panel.stagnant.rowCount(), 1)
        panel.apply_theme(True)
        self.app.processEvents()
        panel.close()


if __name__ == "__main__":
    unittest.main()
