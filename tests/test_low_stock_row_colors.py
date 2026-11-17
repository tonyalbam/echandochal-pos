"""Colores de estado en Productos > Stock bajo / agotado."""

import os
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget

from app.database.schema import create_database
from app.services.product_service import ProductService
from app.ui.products_window import ProductsWindow


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


class LowStockColorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDB()
        create_database(self.db)
        self.service = ProductService(self.db)
        self.ids = {}
        for name, stock, minimum in (
            ("Agotado mínimo 0", 0, 0),
            ("Agotado mínimo 4", 0, 4),
            ("En mínimo", 5, 5),
            ("Debajo del mínimo", 2, 5),
            ("Suficiente", 6, 5),
        ):
            self.ids[name] = self.service.create_product({
                "nombre": name, "existencia": stock, "stock_minimo": minimum,
                "precio": 10, "costo": 5,
            })
        self.ids["Servicio"] = self.service.create_product({
            "nombre": "Taller de prueba", "tipo": "SERVICIO",
            "subtipo_servicio": "Talleres", "precio": 100, "costo": 20,
        })
        inactive_id = self.service.create_product({
            "nombre": "Desactivado", "existencia": 0, "stock_minimo": 2,
        })
        self.service.deactivate_product(inactive_id)
        self.ids["Desactivado"] = inactive_id
        self.window = ProductsWindow(self.db)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.db.close()
        self.app.processEvents()

    def _colored_rows(self):
        table = self.window.low_stock_table
        rows = {}
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            rows[item.data(Qt.ItemDataRole.UserRole)] = row
        return rows

    def _assert_row_color(self, row, background, foreground):
        table = self.window.low_stock_table
        for column in range(table.columnCount()):
            with self.subTest(row=row, column=column):
                item = table.item(row, column)
                self.assertIsNotNone(item)
                self.assertEqual(item.background().color().name(), background.lower())
                self.assertEqual(item.foreground().color().name(), foreground.lower())

    def test_all_cells_yellow_at_or_below_minimum_with_positive_stock(self):
        rows = self._colored_rows()
        for name in ("En mínimo", "Debajo del mínimo"):
            self._assert_row_color(
                rows[self.ids[name]],
                ProductsWindow.LOW_STOCK_BACKGROUND,
                ProductsWindow.LOW_STOCK_FOREGROUND,
            )
        self.assertIn("Stock bajo", self.window.low_stock_table.item(
            rows[self.ids["En mínimo"]], 0
        ).toolTip())

    def test_all_cells_brown_when_stock_is_zero_even_when_minimum_is_zero(self):
        rows = self._colored_rows()
        for name in ("Agotado mínimo 0", "Agotado mínimo 4"):
            self._assert_row_color(
                rows[self.ids[name]],
                ProductsWindow.OUT_OF_STOCK_BACKGROUND,
                ProductsWindow.OUT_OF_STOCK_FOREGROUND,
            )
        self.assertIn("Agotado", self.window.low_stock_table.item(
            rows[self.ids["Agotado mínimo 0"]], 0
        ).toolTip())

    def test_only_low_or_empty_active_physical_products_are_shown(self):
        rows = self._colored_rows()
        self.assertEqual(len(rows), 4)
        self.assertNotIn(self.ids["Suficiente"], rows)
        self.assertNotIn(self.ids["Servicio"], rows)
        self.assertNotIn(self.ids["Desactivado"], rows)

    def test_main_products_grid_does_not_inherit_stock_status_color(self):
        low = self._colored_rows()[self.ids["En mínimo"]]
        self.assertEqual(self.window.low_stock_table.item(low, 0).background().color().name(),
                         ProductsWindow.LOW_STOCK_BACKGROUND.lower())
        main = self.window.table
        for row in range(main.rowCount()):
            cell = main.item(row, 0)
            if cell.data(Qt.ItemDataRole.UserRole) == self.ids["En mínimo"]:
                self.assertNotEqual(
                    cell.background().color().name(),
                    ProductsWindow.LOW_STOCK_BACKGROUND.lower(),
                )
                break
        else:
            self.fail("Producto no encontrado en el grid principal")

    def test_selection_sort_and_filter_preserve_row_id_and_colors(self):
        table = self.window.low_stock_table
        table.sortItems(5, Qt.SortOrder.DescendingOrder)
        rows = self._colored_rows()
        self._assert_row_color(
            rows[self.ids["En mínimo"]],
            ProductsWindow.LOW_STOCK_BACKGROUND,
            ProductsWindow.LOW_STOCK_FOREGROUND,
        )
        table.selectRow(rows[self.ids["Agotado mínimo 0"]])
        self.window.tabs.setCurrentWidget(table)
        self.assertEqual(
            self.window._selected_product_id(),
            self.ids["Agotado mínimo 0"],
        )
        self.window.search.setText("Agotado mínimo 0")
        self.app.processEvents()
        rows = self._colored_rows()
        self.assertEqual(list(rows), [self.ids["Agotado mínimo 0"]])
        self._assert_row_color(
            rows[self.ids["Agotado mínimo 0"]],
            ProductsWindow.OUT_OF_STOCK_BACKGROUND,
            ProductsWindow.OUT_OF_STOCK_FOREGROUND,
        )


if __name__ == "__main__":
    unittest.main()
