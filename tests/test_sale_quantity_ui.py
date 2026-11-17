"""Pruebas de edición de cantidad de la venta (tecla C y doble clic)."""

import os
import sqlite3
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QLineEdit

from app.database.schema import create_database
from app.ui.sale_window import (
    SALE_QUANTITY_HELP,
    ClearOnFocusQuantityInput,
    SaleQuantityDialog,
    SaleWindow,
)


class MemoryDatabase:
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


class SaleQuantityUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.database = MemoryDatabase()
        create_database(self.database)
        self.database.cursor().execute(
            """INSERT INTO productos
               (codigo, nombre, precio, costo, existencia)
               VALUES ('P-1', 'Estambre prueba', 100, 40, 5)"""
        )
        self.database.commit()
        self.window = SaleWindow(self.database)
        self.window.show()
        self.app.processEvents()
        self.product = self.window.service.find_product("P-1")
        self.window._agregar_producto(self.product)
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.database.close()
        self.app.processEvents()

    def test_quantity_column_has_help_in_header_and_cells(self):
        header = self.window.tabla.horizontalHeaderItem(5)
        cell = self.window.tabla.item(0, 5)
        self.assertEqual(header.toolTip(), SALE_QUANTITY_HELP)
        self.assertEqual(cell.toolTip(), SALE_QUANTITY_HELP)
        self.assertIn("doble clic", cell.toolTip())
        self.assertIn("C", cell.toolTip())

    def test_set_final_quantity_recalculates_line_and_sale_totals(self):
        self.assertTrue(self.window._establecer_cantidad(0, 3))
        self.assertEqual(self.window.items[0]["cantidad"], 3)
        self.assertEqual(self.window.tabla.item(0, 5).text(), "3")
        self.assertEqual(self.window.tabla.item(0, 7).text(), "$ 300.00")
        self.assertIn("$ 300.00", self.window.total_label.text())

        self.assertTrue(self.window._establecer_cantidad(0, 2))
        self.assertEqual(self.window.items[0]["cantidad"], 2)
        self.assertEqual(self.window.tabla.item(0, 7).text(), "$ 200.00")
        self.assertIn("$ 200.00", self.window.total_label.text())

        self.window.descuento.setValue(20)
        self.assertIn("$ 180.00", self.window.total_label.text())

    def test_entering_zero_removes_row(self):
        self.assertTrue(self.window._establecer_cantidad(0, 0))
        self.assertEqual(self.window.items, [])
        self.assertEqual(self.window.tabla.rowCount(), 0)
        self.assertIn("$ 0.00", self.window.total_label.text())

    def test_same_product_multiple_rows_share_inventory(self):
        self.window._agregar_producto(self.product)
        self.assertEqual(self.window.tabla.rowCount(), 2)
        self.assertTrue(self.window._establecer_cantidad(0, 4))
        self.assertEqual([i["cantidad"] for i in self.window.items], [4, 1])

        with patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(self.window._establecer_cantidad(0, 5))
            warning.assert_called_once()
        self.assertEqual([i["cantidad"] for i in self.window.items], [4, 1])
        self.assertIn("$ 500.00", self.window.total_label.text())

    def test_uses_current_inventory_not_old_cached_stock(self):
        self.database.cursor().execute(
            "UPDATE productos SET existencia = 2 WHERE codigo = 'P-1'"
        )
        self.database.commit()
        with patch.object(QMessageBox, "warning"):
            self.assertFalse(self.window._establecer_cantidad(0, 3))
        self.assertEqual(self.window.items[0]["cantidad"], 1)
        self.assertTrue(self.window._establecer_cantidad(0, 2))
        self.assertEqual(self.window.items[0]["cantidad"], 2)

    def test_dialog_has_single_integer_field_and_no_operation_selector(self):
        dialog = SaleQuantityDialog(self.window.items, 0, 5, self.window)
        dialog.show()
        self.app.processEvents()
        self.assertIsInstance(dialog.quantity, ClearOnFocusQuantityInput)
        self.assertIsInstance(dialog.quantity, QLineEdit)
        self.assertIsNotNone(dialog.quantity.validator())
        self.assertFalse(hasattr(dialog, "operation"))
        self.assertEqual(dialog.quantity.text(), "")
        self.assertFalse(dialog.apply_button.isEnabled())
        dialog.close()

    def test_input_clears_on_every_focus_and_rejects_decimal_typing(self):
        dialog = SaleQuantityDialog(self.window.items, 0, 5, self.window)
        dialog.show()
        self.app.processEvents()
        dialog.quantity.setText("3")
        dialog.quantity.clearFocus()
        self.app.processEvents()
        dialog.quantity.setFocus()
        self.app.processEvents()
        self.assertEqual(dialog.quantity.text(), "")
        QTest.keyClicks(dialog.quantity, "2.5")
        self.assertNotIn(".", dialog.quantity.text())
        dialog.close()

    def test_dialog_previews_new_total_and_blocks_overstock(self):
        dialog = SaleQuantityDialog(self.window.items, 0, 5, self.window)
        dialog.show()
        self.app.processEvents()
        dialog.quantity.setText("5")
        self.assertTrue(dialog.apply_button.isEnabled())
        self.assertIn("$ 500.00", dialog.preview.text())

        dialog.quantity.setText("6")
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertIn("Inventario insuficiente", dialog.preview.text())
        dialog.quantity.setText("0")
        self.assertTrue(dialog.apply_button.isEnabled())
        self.assertIn("quitará", dialog.preview.text())
        dialog.close()

    def test_enter_applies_final_quantity(self):
        dialog = SaleQuantityDialog(self.window.items, 0, 5, self.window)
        dialog.show()
        self.app.processEvents()
        dialog.quantity.setText("4")
        QTest.keyClick(dialog.quantity, Qt.Key.Key_Return)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.new_quantity, 4)
        dialog.close()

    def test_enter_with_invalid_quantity_does_not_accept(self):
        dialog = SaleQuantityDialog(self.window.items, 0, 5, self.window)
        dialog.show()
        self.app.processEvents()
        dialog.quantity.setText("41")
        self.assertFalse(dialog.apply_button.isEnabled())
        QTest.keyClick(dialog.quantity, Qt.Key.Key_Return)
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertIsNone(dialog.new_quantity)
        dialog.close()

    def test_double_click_opens_edit_dialog(self):
        with patch("app.ui.sale_window.SaleQuantityDialog") as cls:
            cls.return_value.exec.return_value = QDialog.DialogCode.Accepted
            cls.return_value.new_quantity = 3
            self.window.tabla.cellDoubleClicked.emit(0, 1)
            cls.return_value.exec.assert_called_once()
        self.assertEqual(self.window.items[0]["cantidad"], 3)

    def test_volume_mode_checkbox_is_removed(self):
        self.assertFalse(hasattr(self.window, "venta_voluminosa"))
    def test_each_row_keeps_its_own_editable_quantity(self):
        # Escanear el mismo producto vuelve a agregar una fila independiente.
        self.assertTrue(self.window._establecer_cantidad(0, 3))
        self.window._agregar_producto(self.product)
        self.assertEqual(self.window.tabla.rowCount(), 2)
        self.assertEqual([item["cantidad"] for item in self.window.items], [3, 1])
        self.assertTrue(self.window._establecer_cantidad(1, 2))
        self.assertEqual([item["cantidad"] for item in self.window.items], [3, 2])
        self.assertEqual(self.window.tabla.item(0, 7).text(), "$ 300.00")
        self.assertEqual(self.window.tabla.item(1, 7).text(), "$ 200.00")
        self.assertIn("$ 500.00", self.window.total_label.text())

    def test_sale_service_rejects_duplicate_rows_above_current_stock(self):
        self.window._agregar_producto(self.product)
        self.window.items[0]["cantidad"] = 4
        self.window.items[1]["cantidad"] = 2
        with self.assertRaisesRegex(ValueError, "Existencia insuficiente"):
            self.window.service.create_sale(self.window.items)
        count = self.database.connection.execute(
            "SELECT COUNT(*) FROM ventas"
        ).fetchone()[0]
        self.assertEqual(count, 0)
        stock = self.database.connection.execute(
            "SELECT existencia FROM productos WHERE codigo = 'P-1'"
        ).fetchone()[0]
        self.assertEqual(stock, 5)

    def test_c_key_from_selected_row_opens_edit_dialog(self):
        self.window.tabla.selectRow(0)
        self.window.tabla.setFocus()
        self.app.processEvents()
        with patch("app.ui.sale_window.SaleQuantityDialog") as cls:
            cls.return_value.exec.return_value = QDialog.DialogCode.Accepted
            cls.return_value.new_quantity = 2
            QTest.keyClick(self.window.tabla, Qt.Key.Key_C)
            cls.return_value.exec.assert_called_once()
        self.assertEqual(self.window.items[0]["cantidad"], 2)


if __name__ == "__main__":
    unittest.main()
