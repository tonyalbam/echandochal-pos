"""Comportamiento del campo Descuento en Nueva Venta."""

import os
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractSpinBox, QDoubleSpinBox

from app.database.schema import create_database
from app.ui.sale_window import ClearOnFocusDiscountSpinBox, SaleWindow


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


class SaleDiscountUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.database = MemoryDatabase()
        create_database(self.database)
        self.database.cursor().execute(
            """INSERT INTO productos (codigo, nombre, precio, costo, existencia)
               VALUES ('D-1', 'Prueba descuento', 100, 50, 10)"""
        )
        self.database.commit()
        self.window = SaleWindow(self.database)
        self.window.show()
        self.app.processEvents()
        self.window._agregar_producto(self.window.service.find_product("D-1"))
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.database.close()
        self.app.processEvents()

    def _focus_discount_again(self):
        self.window.codigo_input.setFocus()
        self.app.processEvents()
        self.window.descuento.setFocus()
        self.app.processEvents()

    def test_discount_field_without_arrows_in_both_modes(self):
        discount = self.window.descuento
        self.assertIsInstance(discount, ClearOnFocusDiscountSpinBox)
        self.assertIsInstance(discount, QDoubleSpinBox)
        self.assertEqual(
            discount.buttonSymbols(), QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.window.descuento_tipo.setCurrentText("Porcentaje")
        self.assertEqual(
            discount.buttonSymbols(), QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.assertEqual(discount.maximum(), 100.0)

    def test_amount_clears_on_focus_and_can_be_typed(self):
        discount = self.window.descuento
        discount.setValue(15.0)
        self.assertIn("$ 85.00", self.window.total_label.text())
        self._focus_discount_again()
        self.assertEqual(discount.value(), 0)
        self.assertNotIn("15.00", discount.text())
        self.assertIn("$ 100.00", self.window.total_label.text())
        QTest.keyClicks(discount, "25")
        self.assertAlmostEqual(discount.value(), 25)
        self.assertIn("$ 75.00", self.window.total_label.text())

    def test_percentage_clears_on_focus_and_recalculates(self):
        discount = self.window.descuento
        self.window.descuento_tipo.setCurrentText("Porcentaje")
        discount.setValue(30)
        self.assertIn("$ 70.00", self.window.total_label.text())
        self._focus_discount_again()
        self.assertEqual(discount.value(), 0)
        self.assertNotIn("30.00", discount.text())
        self.assertIn("$ 100.00", self.window.total_label.text())
        QTest.keyClicks(discount, "10")
        self.assertAlmostEqual(discount.value(), 10)
        self.assertIn("$ 90.00", self.window.total_label.text())

    def test_focus_clears_on_every_new_entry(self):
        discount = self.window.descuento
        discount.setValue(14)
        self._focus_discount_again()
        self.assertEqual(discount.value(), 0)
        QTest.keyClicks(discount, "7")
        self._focus_discount_again()
        self.assertEqual(discount.value(), 0)
        self.assertNotIn("7.00", discount.text())

    def test_amount_and_percentage_limits_are_preserved(self):
        discount = self.window.descuento
        self.assertEqual(discount.minimum(), 0.0)
        self.assertEqual(discount.maximum(), 999999.99)
        self.assertEqual(discount.decimals(), 2)
        self.window.descuento_tipo.setCurrentText("Porcentaje")
        self.assertEqual(discount.maximum(), 100.0)
        discount.setValue(110)
        self.assertEqual(discount.value(), 100.0)
        self.window.descuento_tipo.setCurrentText("Monto")
        self.assertEqual(discount.maximum(), 999999.99)


if __name__ == "__main__":
    unittest.main()
