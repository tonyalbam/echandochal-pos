"""Venta: confirmación ágil y envío de recibo a impresora predeterminada."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from pypdf import PdfReader

from app.database.schema import create_database
from app.services.ticket_service import TicketService
from app.ui.sale_receipt_prompt import SaleReceiptPrompt
from app.ui.sale_window import SaleWindow
from app.ui.ticket_preview_dialog import print_sale_ticket_to_printer


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


class SaleReceiptPromptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.sale = {"folio": "V-0001", "total": 150.0, "change": 25.0}

    def _prompt(self):
        dialog = SaleReceiptPrompt(self.sale)
        dialog.show()
        self.app.processEvents()
        return dialog

    def test_compact_dialog_shows_sale_and_two_actions(self):
        dialog = self._prompt()
        try:
            self.assertTrue(dialog.print_button.isDefault())
            self.assertIn("C / Esc", dialog.skip_button.text())
            self.assertIn("Enter", dialog.print_button.text())
            self.assertEqual(
                dialog.findChildren(type(dialog.print_button)).__len__(), 2
            )
            self.assertIn("Venta registrada", dialog.windowTitle())
        finally:
            dialog.close()

    def test_c_key_cancels_printing(self):
        dialog = self._prompt()
        QTest.keyClick(dialog, Qt.Key.Key_C)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        dialog.close()

    def test_escape_key_cancels_printing(self):
        dialog = self._prompt()
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        dialog.close()

    def test_close_window_cancels_printing(self):
        dialog = self._prompt()
        dialog.close()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

    def test_click_no_print_cancels(self):
        dialog = self._prompt()
        dialog.skip_button.click()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        dialog.close()

    def test_enter_and_i_confirm_printing(self):
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_I):
            with self.subTest(key=key):
                dialog = self._prompt()
                QTest.keyClick(dialog, key)
                self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
                dialog.close()


class SalePostPaymentPrintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO productos
               (codigo, nombre, precio, costo, existencia)
               VALUES ('POS-001', 'Estambre de prueba', 100, 50, 5)"""
        )
        self.db.commit()
        self.window = SaleWindow(self.db)
        self.window.show()
        self.app.processEvents()
        self.window._agregar_producto(
            self.window.service.find_product("POS-001")
        )

    def tearDown(self):
        self.window.close()
        self.db.close()
        self.app.processEvents()

    def _complete_checkout(self, should_print: bool):
        with patch("app.ui.sale_window.SalePaymentDialog") as payment, \
             patch("app.ui.sale_window.SaleReceiptPrompt") as prompt, \
             patch.object(self.window, "_imprimir_ultimo_ticket") as printed:
            payment.return_value.exec.return_value = QDialog.DialogCode.Accepted
            payment.return_value.result = {
                "payments": {
                    "Efectivo": 100.0, "Transferencia": 0.0,
                    "Mercado Libre": 0.0,
                },
                "cash_received": 100.0,
            }
            prompt.return_value.exec.return_value = (
                QDialog.DialogCode.Accepted if should_print
                else QDialog.DialogCode.Rejected
            )

            self.window._cobrar()

            payment.return_value.exec.assert_called_once()
            prompt.return_value.exec.assert_called_once()
            created_sale = prompt.call_args.args[0]
            self.assertEqual(created_sale["id"], self.window.last_sale_id)
            self.assertEqual(created_sale["total"], 100.0)
            self.assertEqual(printed.call_count, int(should_print))

        self.assertEqual(self.window.items, [])
        self.assertTrue(self.window.ticket_button.isEnabled())
        self.assertEqual(
            self.db.connection.execute("SELECT COUNT(*) FROM ventas").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.db.connection.execute(
                "SELECT existencia FROM productos WHERE codigo = 'POS-001'"
            ).fetchone()[0],
            4.0,
        )

    def test_skip_print_preserves_sale_and_inventory(self):
        self._complete_checkout(False)

    def test_print_confirmation_issues_only_one_print(self):
        self._complete_checkout(True)

    def test_no_printer_shows_warning_without_undoing_sale(self):
        self._complete_checkout(False)
        with patch("app.ui.sale_window.QPrinterInfo.defaultPrinter") as info, \
             patch.object(QMessageBox, "warning") as warning:
            info.return_value.isNull.return_value = True
            self.window._imprimir_ultimo_ticket()
            warning.assert_called_once()
        self.assertEqual(
            self.db.connection.execute("SELECT COUNT(*) FROM ventas").fetchone()[0],
            1,
        )

    def test_print_to_virtual_printer_without_print_or_save_dialog(self):
        self._complete_checkout(False)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "impresora_simulada.pdf"
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(str(output))
            print_sale_ticket_to_printer(
                TicketService(self.db), self.window.last_sale_id, printer
            )
            self.assertTrue(output.is_file())
            self.assertEqual(len(PdfReader(output).pages), 1)
            text = PdfReader(output).pages[0].extract_text()
            # El trabajo de impresión reproduce el ticket, no crea otra venta.
            self.assertEqual(
                self.db.connection.execute(
                    "SELECT COUNT(*) FROM ventas"
                ).fetchone()[0], 1
            )


if __name__ == "__main__":
    unittest.main()
