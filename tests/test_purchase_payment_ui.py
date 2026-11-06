"""Interfaz de desembolsos mixtos de compras."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit

from app.ui.purchase_window import PurchasePaymentDialog
from app.services.purchase_service import PurchaseService


class PurchasePaymentDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = PurchasePaymentDialog(250)
        self.dialog.show()
        self.app.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.app.processEvents()

    def test_empty_equally_aligned_money_fields_without_arrows(self):
        self.assertEqual(
            tuple(self.dialog.amounts), PurchaseService.PAYMENT_METHODS
        )
        fields = list(self.dialog.amounts.values())
        for field in fields:
            self.assertIsInstance(field, QLineEdit)
            self.assertNotIsInstance(field, QDoubleSpinBox)
            self.assertEqual(field.text(), "")
            self.assertEqual(field.currency_prefix.text(), "$")
        self.assertEqual(len({f.width() for f in fields}), 1)
        self.assertFalse(self.dialog.confirm.isEnabled())

    def test_payment_split_enables_confirmation_only_when_balanced(self):
        fields = self.dialog.amounts
        fields["Efectivo"].setText("50")
        fields["Tarjeta"].setText("100")
        self.assertFalse(self.dialog.confirm.isEnabled())
        self.assertIn("100.00", self.dialog.remaining.text())
        fields["Transferencia"].setText("100")
        self.assertTrue(self.dialog.confirm.isEnabled())
        self.dialog._accept()
        self.assertEqual(
            self.dialog.result,
            {"Efectivo": 50, "Tarjeta": 100, "Transferencia": 100},
        )

    def test_refocusing_clears_old_amount(self):
        cash = self.dialog.amounts["Efectivo"]
        other = self.dialog.amounts["Tarjeta"]
        cash.setFocus()
        QTest.keyClicks(cash, "120.50")
        self.assertEqual(cash.amount(), 120.50)
        other.setFocus()
        cash.setFocus()
        self.assertEqual(cash.text(), "")
        self.assertEqual(cash.amount(), 0)


if __name__ == "__main__":
    unittest.main()
