"""Ventanas de historial: ventas canceladas se distinguen en rojo, como Productos."""
import os
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from app.database.schema import create_database
from app.ui.sale_history_window import SaleHistoryWindow
from app.ui.theme import theme_colors


class MemoryDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


class CancelledSaleRowColorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.previous_theme = self.app.property("echandochal_dark_mode")
        self.app.setProperty("echandochal_dark_mode", False)
        self.db = MemoryDatabase()
        create_database(self.db)
        self.db.cursor().executemany(
            """INSERT INTO ventas
               (folio, fecha, hora, subtotal, total, metodo_pago,
                monto_comision, total_neto, cancelada)
               VALUES (?, ?, '12:00:00', ?, ?, 'Efectivo', 0, ?, ?)""",
            (
                ("V-ACTIVA", "2026-11-05", 100, 100, 100, 0),
                ("V-CANCELADA", "2026-11-06", 150, 150, 150, 1),
                ("V-OCTUBRE", "2026-10-04", 200, 200, 200, 0),
            ),
        )
        self.db.commit()
        self.window = SaleHistoryWindow(self.db)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.db.close()
        self.app.setProperty("echandochal_dark_mode", self.previous_theme)

    def _items(self):
        def leaves(item):
            if item.data(0, Qt.ItemDataRole.UserRole) is not None:
                yield item
            for index in range(item.childCount()):
                yield from leaves(item.child(index))
        result = {}
        for index in range(self.window.tabla.topLevelItemCount()):
            for item in leaves(self.window.tabla.topLevelItem(index)):
                result[item.text(0)] = item
        return result

    def _assert_red_row(self, item, dark):
        expected = QColor(theme_colors(dark)["danger_row"])
        foreground = QColor(theme_colors(dark)["text"])
        for column in range(9):
            with self.subTest(column=column):
                self.assertEqual(item.background(column).color(), expected)
                self.assertEqual(item.foreground(column).color(), foreground)
        self.assertEqual(item.text(8), "CANCELADA")

    def test_only_cancelled_rows_are_red_across_all_nine_columns(self):
        items = self._items()
        self.assertEqual(set(items), {"V-ACTIVA", "V-CANCELADA", "V-OCTUBRE"})
        self._assert_red_row(items["V-CANCELADA"], False)
        for folio in ("V-ACTIVA", "V-OCTUBRE"):
            self.assertEqual(items[folio].background(0).style(),
                             Qt.BrushStyle.NoBrush)
            self.assertEqual(items[folio].text(8), "ACTIVA")

    def test_grouped_by_month_keeps_cancellation_color_and_group_headers_neutral(self):
        self.window.agrupar.setCurrentText("Año y mes")
        self.assertEqual(self.window.tabla.topLevelItemCount(), 1)
        year = self.window.tabla.topLevelItem(0)
        self.assertEqual(year.text(0), "2026")
        self.assertEqual(year.background(0).style(), Qt.BrushStyle.NoBrush)
        for month_index in range(year.childCount()):
            self.assertEqual(
                year.child(month_index).background(0).style(),
                Qt.BrushStyle.NoBrush,
            )
        self._assert_red_row(self._items()["V-CANCELADA"], False)
        # Ordenar por importe y volver a cargar no debe perder identidad/color.
        self.window._sort_sales(6)
        self.window.refresh()
        self._assert_red_row(self._items()["V-CANCELADA"], False)
        sale_id = self._items()["V-CANCELADA"].data(
            0, Qt.ItemDataRole.UserRole
        )
        self.assertEqual(self.window.sales_by_id[sale_id]["folio"], "V-CANCELADA")

    def test_dark_mode_matches_inactive_products_danger_color(self):
        self.app.setProperty("echandochal_dark_mode", True)
        self.window.refresh()
        self._assert_red_row(self._items()["V-CANCELADA"], True)

    def test_cancelled_filter_hides_red_rows_and_restores_them(self):
        self.window.mostrar_canceladas.setChecked(False)
        self.assertNotIn("V-CANCELADA", self._items())
        self.window.mostrar_canceladas.setChecked(True)
        self._assert_red_row(self._items()["V-CANCELADA"], False)

    def test_cancellation_state_change_recolors_on_refresh(self):
        self.db.cursor().execute(
            "UPDATE ventas SET cancelada = 1 WHERE folio = ?",
            ("V-ACTIVA",),
        )
        self.db.commit()
        self.window.refresh()
        self._assert_red_row(self._items()["V-ACTIVA"], False)


if __name__ == "__main__":
    unittest.main()
