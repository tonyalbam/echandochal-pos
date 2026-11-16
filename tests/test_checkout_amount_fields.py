"""Regresión de cobro sin importe de efectivo duplicado."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit, QLabel

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

    def test_only_three_fields_empty_without_spin_buttons(self):
        self.assertEqual(tuple(self.dialog.amounts), (
            "Transferencia", "Mercado Libre"
        ))
        fields = list(self.dialog.amounts.values()) + [
            self.dialog.cash_received
        ]
        self.assertEqual(len(fields), 3)
        self.assertNotIn("Efectivo", self.dialog.amounts)
        for field in fields:
            with self.subTest(field=field.accessibleName()):
                self.assertIsInstance(field, PaymentAmountInput)
                self.assertIsInstance(field, QLineEdit)
                self.assertNotIsInstance(field, QDoubleSpinBox)
                self.assertEqual(field.text(), "")
                self.assertEqual(field.amount(), 0.0)
        self.assertFalse(self.dialog.confirm.isEnabled())
        self.assertIn("$ 350.00", self.dialog.remaining_label.text())
        self.assertIn("$ 350.00", self.dialog.cash_applied_label.text())

    def test_currency_prefix_visible_and_all_inputs_aligned(self):
        fields = list(self.dialog.amounts.values()) + [
            self.dialog.cash_received
        ]
        self.app.processEvents()
        self.assertEqual(len({field.geometry().x() for field in fields}), 1)
        self.assertEqual(len({field.width() for field in fields}), 1)
        for field in fields:
            with self.subTest(field=field.accessibleName()):
                self.assertEqual(field.currency_prefix.text(), "$")
                self.assertTrue(field.currency_prefix.isVisible())
                self.assertGreater(field.textMargins().left(), 0)
                field.setFocus()
                QTest.keyClicks(field, "89.50")
                self.assertEqual(field.text(), "89.50")
                self.assertEqual(field.amount(), 89.5)
                field.clear()

    def test_focusing_existing_entry_clears_entire_amount(self):
        cash = self.dialog.cash_received
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

    def test_mixed_payment_computes_cash_due_and_change_automatically(self):
        for field, value in (
            (self.dialog.amounts["Transferencia"], "100"),
            (self.dialog.amounts["Mercado Libre"], "200"),
            (self.dialog.cash_received, "100"),
        ):
            field.setFocus()
            QTest.keyClicks(field, value)
        self.assertTrue(self.dialog.confirm.isEnabled())
        self.assertIn("$ 50.00", self.dialog.cash_applied_label.text())
        self.assertIn("$ 0.00", self.dialog.remaining_label.text())
        self.assertIn("$ 50.00", self.dialog.change_label.text())
        self.assertIn("$ 8.00", self.dialog.commission_label.text())
        self.dialog._accept()
        self.assertIsNotNone(self.dialog.result)
        self.assertEqual(self.dialog.result["payments"], {
            "Efectivo": 50, "Transferencia": 100, "Mercado Libre": 200
        })
        self.assertEqual(self.dialog.result["change"], 50)
        self.assertEqual(self.dialog.result["cash_received"], 100)

    def test_cash_only_computes_change_and_no_card_commission(self):
        self.dialog.cash_received.setText("400")
        self.assertTrue(self.dialog.confirm.isEnabled())
        self.assertIn("$ 50.00", self.dialog.change_label.text())
        self.dialog._accept()
        self.assertEqual(self.dialog.result["payments"]["Efectivo"], 350)
        self.assertEqual(self.dialog.result["change"], 50)
        self.assertEqual(self.dialog.result["commission"], 0)

    def test_insufficient_cash_is_disabled_without_registering_payment(self):
        self.dialog.amounts["Transferencia"].setText("100")
        self.dialog.cash_received.setText("200")
        self.assertFalse(self.dialog.confirm.isEnabled())
        self.assertIn("$ 50.00", self.dialog.remaining_label.text())
        self.assertIn("$ 0.00", self.dialog.change_label.text())

    def test_electronic_payments_over_total_cannot_be_confirmed(self):
        self.dialog.amounts["Transferencia"].setText("200")
        self.dialog.amounts["Mercado Libre"].setText("200")
        self.dialog.cash_received.setText("100")
        self.assertFalse(self.dialog.confirm.isEnabled())
        self.assertIn("exceden el total", self.dialog.remaining_label.text())
        self.assertIn("$ 50.00", self.dialog.remaining_label.text())

    def test_amount_validator_limits_decimals_and_rejects_letters(self):
        field = self.dialog.cash_received
        field.setFocus()
        QTest.keyClicks(field, "12.345abc")
        self.assertEqual(field.text(), "12.34")
        self.assertEqual(field.amount(), 12.34)

    def test_only_card_does_not_require_cash_received(self):
        self.dialog.amounts["Mercado Libre"].setText("350")
        self.assertTrue(self.dialog.confirm.isEnabled())
        self.assertEqual(self.dialog.cash_received.text(), "")
        self.dialog._accept()
        self.assertEqual(self.dialog.result["payments"]["Mercado Libre"], 350)
        self.assertEqual(self.dialog.result["payments"]["Efectivo"], 0)
        self.assertEqual(self.dialog.result["change"], 0)

    def test_when_electronic_payments_cover_all_cash_is_returned_entirely(self):
        self.dialog.amounts["Transferencia"].setText("350")
        self.dialog.cash_received.setText("50")
        self.assertTrue(self.dialog.confirm.isEnabled())
        self.assertIn("$ 0.00", self.dialog.cash_applied_label.text())
        self.assertIn("$ 50.00", self.dialog.change_label.text())
        self.dialog._accept()
        self.assertEqual(self.dialog.result["payments"]["Efectivo"], 0)
        self.assertEqual(self.dialog.result["change"], 50)


if __name__ == "__main__":
    unittest.main()
