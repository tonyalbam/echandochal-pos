"""Regresión de usabilidad de montos de cobro: captura manual desde cero."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit

from app.ui.sale_window import PaymentAmountInput, SalePaymentDialog


class CheckoutInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = SalePaymentDialog(350, 4)
        self.dialog.show()
        self.app.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.app.processEvents()

    def test_all_four_fields_are_empty_text_inputs_without_spin_buttons(self):
        fields = list(self.dialog.amounts.values()) + [
            self.dialog.cash_received
        ]
        self.assertEqual(len(fields), 4)
        for field in fields:
            with self.subTest(field=field.accessibleName()):
                self.assertIsInstance(field, QLineEdit)
                self.assertIsInstance(field, PaymentAmountInput)
                self.assertNotIsInstance(field, QDoubleSpinBox)
                self.assertEqual(field.text(), "")
                self.assertEqual(field.amount(), 0.0)
        self.assertFalse(self.dialog.confirm.isEnabled())
        self.assertIn("$ 350.00", self.dialog.remaining_label.text())

    def test_focusing_existing_entry_clears_entire_amount(self):
        cash = self.dialog.amounts["Efectivo"]
        transfer = self.dialog.amounts["Transferencia"]
        cash.setFocus()
        QTest.keyClicks(cash, "120.50")
        self.assertEqual(cash.text(), "120.50")
        transfer.setFocus()
        self.app.processEvents()
        cash.setFocus()
        self.app.processEvents()
        self.assertEqual(cash.text(), "")
        self.assertEqual(cash.amount(), 0.0)

    def test_mixed_payment_updates_totals_and_final_result(self):
        cash = self.dialog.amounts["Efectivo"]
        transfer = self.dialog.amounts["Transferencia"]
        card = self.dialog.amounts["Mercado Libre"]
        for field, value in (
            (cash, "50"), (transfer, "100"), (card, "200"),
            (self.dialog.cash_received, "100"),
        ):
            field.setFocus()
            QTest.keyClicks(field, value)
        self.assertTrue(self.dialog.confirm.isEnabled())
        self.assertIn("$ 0.00", self.dialog.remaining_label.text())
        self.assertIn("$ 50.00", self.dialog.change_label.text())
        self.assertIn("$ 8.00", self.dialog.commission_label.text())
        self.dialog._accept()
        self.assertIsNotNone(self.dialog.result)
        self.assertEqual(self.dialog.result["payments"]["Efectivo"], 50)
        self.assertEqual(self.dialog.result["payments"]["Transferencia"], 100)
        self.assertEqual(self.dialog.result["payments"]["Mercado Libre"], 200)

    def test_amount_validator_limits_decimals_and_rejects_letters(self):
        field = self.dialog.amounts["Efectivo"]
        field.setFocus()
        QTest.keyClicks(field, "12.345abc")
        self.assertEqual(field.text(), "12.34")
        self.assertEqual(field.amount(), 12.34)

    def test_cash_received_is_optional_when_only_card_is_charged(self):
        card = self.dialog.amounts["Mercado Libre"]
        card.setFocus()
        QTest.keyClicks(card, "350")
        self.assertTrue(self.dialog.confirm.isEnabled())
        self.assertEqual(self.dialog.cash_received.text(), "")
        self.dialog._accept()
        self.assertEqual(
            self.dialog.result["payments"]["Mercado Libre"], 350
        )


if __name__ == "__main__":
    unittest.main()
