import os
import sqlite3
import unittest
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit, QSpinBox, QDoubleSpinBox
from PySide6.QtTest import QTest

from app.database.schema import create_database
from app.ui.cash_closing_window import CashClosingWindow, ClearOnFocusAmount


class MemoryDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        return self.connection.commit()

    def rollback(self):
        return self.connection.rollback()


class CashClosingUiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.database = MemoryDatabase()
        create_database(self.database)
        self.window = CashClosingWindow(self.database)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.database.connection.close()

    def test_all_inputs_are_empty_and_have_no_spin_arrows(self):
        fields = list(self.window.cash_inputs.values()) + [
            self.window.loose_change
        ]
        self.assertGreater(len(fields), 1)
        for field in fields:
            with self.subTest(field=field.objectName()):
                self.assertIsInstance(field, ClearOnFocusAmount)
                self.assertIsInstance(field, QLineEdit)
                self.assertNotIsInstance(field, QSpinBox)
                self.assertNotIsInstance(field, QDoubleSpinBox)
                self.assertEqual(field.text(), "")
                self.assertEqual(field.amount(), 0)

    def test_count_fields_accept_only_integer_quantities(self):
        quantity = next(iter(self.window.cash_inputs.values()))
        quantity.setFocus()
        QTest.keyClicks(quantity, "12.5abc")
        self.assertEqual(quantity.text(), "125")
        self.assertEqual(quantity.amount(), 125)

    def test_focus_clears_previous_quantity_without_affecting_other_fields(self):
        fields = list(self.window.cash_inputs.values())
        first, second = fields[:2]
        first.setFocus()
        QTest.keyClicks(first, "3")
        second.setFocus()
        QTest.keyClicks(second, "2")
        self.assertEqual(self.window._cash_counts()[list(self.window.cash_inputs)[0]], 3)
        first.setFocus()
        self.app.processEvents()
        self.assertEqual(first.text(), "")
        self.assertEqual(second.text(), "2")

    def test_loose_change_accepts_two_decimals_and_clears_when_refocused(self):
        field = self.window.loose_change
        field.setFocus()
        QTest.keyClicks(field, "21.50")
        self.assertEqual(field.amount(), 21.5)
        first = next(iter(self.window.cash_inputs.values()))
        first.setFocus()
        field.setFocus()
        self.app.processEvents()
        self.assertEqual(field.text(), "")
        self.assertEqual(field.amount(), 0.0)

    def test_reconciliation_still_uses_entered_counts_and_change(self):
        (kind, denomination), first = next(iter(self.window.cash_inputs.items()))
        first.setFocus()
        QTest.keyClicks(first, "2")
        self.window.loose_change.setFocus()
        QTest.keyClicks(self.window.loose_change, "12.50")
        self.assertEqual(self.window._cash_counts()[(kind, denomination)], 2)
        expected = denomination * 2 + 12.50
        self.assertIn(f"{expected:,.2f}", self.window.cash_counted.text())

    def test_date_changed_clears_all_entries(self):
        first = next(iter(self.window.cash_inputs.values()))
        first.setFocus()
        QTest.keyClicks(first, "5")
        self.window.loose_change.setFocus()
        QTest.keyClicks(self.window.loose_change, "8.50")
        self.window._date_changed()
        self.assertEqual(first.text(), "")
        self.assertEqual(self.window.loose_change.text(), "")


if __name__ == "__main__":
    unittest.main()
