"""Interacción en Qt: gastos de caja chica y cierre confirmado."""
import os
import sqlite3
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QMessageBox

from app.database.schema import create_database
from app.ui.cash_closing_window import CashClosingWindow


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


class PettyCashUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO ventas
               (folio, fecha, hora, total, subtotal, metodo_pago, total_neto)
               VALUES ('UI-CASH-1', '2026-10-01', '10:00:00', 70, 70, 'Efectivo', 70)"""
        )
        cursor.execute(
            """INSERT INTO pagos_venta (venta_id, metodo_pago, monto)
               VALUES (?, 'Efectivo', 70)""", (cursor.lastrowid,)
        )
        self.db.commit()
        self.window = CashClosingWindow(self.db)
        self.window.date.setDate(QDate(2026, 10, 1))
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.db.connection.close()

    def test_confirm_closure_and_carry_over_to_next_date(self):
        self.assertTrue(self.window.confirm_closing_button.isEnabled())
        self.assertEqual(self.window.cash_sales.text(), "$ 70.00")
        self.window.cash_inputs[("Billete", 50.0)].setText("1")
        self.window.cash_inputs[("Billete", 20.0)].setText("1")
        self.assertEqual(self.window.cash_status.text(), "CUADRA")
        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch.object(QMessageBox, "information"):
            self.window._confirm_closing()
        self.assertFalse(self.window.confirm_closing_button.isEnabled())
        self.assertEqual(self.window.cash_status.text(), "CONFIRMADO")
        self.assertEqual(self.window.cash_counted.text(), "$ 70.00")
        self.assertTrue(self.window.loose_change.isReadOnly())
        self.window.date.setDate(QDate(2026, 10, 2))
        self.app.processEvents()
        self.assertEqual(self.window.opening_cash.text(), "$ 70.00")
        self.assertEqual(self.window.cash_expected.text(), "$ 70.00")
        self.assertTrue(self.window.confirm_closing_button.isEnabled())

    def test_register_and_void_variable_expense_via_interface(self):
        self.window.expense_type.setCurrentText("Gastos variables")
        self.window.expense_description.setText("Papelería")
        self.window.expense_amount.setText("25.50")
        self.window._register_expense()
        self.assertEqual(self.window.expenses_table.rowCount(), 1)
        self.assertEqual(self.window.operating_expenses.text(), "$ 25.50")
        self.assertEqual(self.window.cash_expected.text(), "$ 44.50")
        self.window.expenses_table.selectRow(0)
        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            self.window._remove_expense()
        self.assertEqual(self.window.expenses_table.rowCount(), 0)
        self.assertEqual(self.window.operating_expenses.text(), "$ 0.00")

    def test_fund_registration_is_visible_and_one_time(self):
        self.assertTrue(self.window.initial_fund_button.isEnabled())
        self.window.initial_fund_amount.setText("30")
        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            self.window._register_initial_fund()
        self.assertEqual(self.window.opening_cash.text(), "$ 30.00")
        self.assertFalse(self.window.initial_fund_button.isEnabled())
        self.assertEqual(self.window.cash_expected.text(), "$ 100.00")


if __name__ == "__main__":
    unittest.main()
