"""Pruebas del visor interno y la impresión de tickets en Historial de ventas."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPageSize
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication
from pypdf import PdfReader

from app.database.schema import create_database
from app.services.sale_service import SaleService
from app.ui.sale_history_window import SaleHistoryWindow
from app.ui.ticket_preview_dialog import TicketPreviewDialog, print_pdf_document


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


class TicketPreviewUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.database = MemoryDatabase()
        create_database(self.database)
        cursor = self.database.cursor()
        cursor.execute(
            """INSERT INTO productos (codigo, nombre, costo, precio, existencia)
               VALUES ('PDF-001', 'Ovillo de prueba', 20, 50, 10)"""
        )
        product_id = int(cursor.lastrowid)
        self.database.commit()
        self.sale = SaleService(self.database).create_sale(
            [{"producto_id": product_id, "cantidad": 2, "precio_unitario": 50}],
            payment_method="Efectivo",
        )
        self.window = SaleHistoryWindow(self.database)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.database.close()
        self.app.processEvents()

    def _select_sale(self):
        item = self.window.tabla.topLevelItem(0)
        self.assertIsNotNone(item)
        self.window.tabla.setCurrentItem(item)
        self.app.processEvents()

    def test_view_button_enabled_only_for_selected_sale(self):
        self.assertFalse(self.window.ver_ticket.isEnabled())
        self._select_sale()
        self.assertTrue(self.window.ver_ticket.isEnabled())
        self.assertTrue(self.window.ticket.isEnabled())

    def test_preview_opens_and_removes_only_temporary_file(self):
        self._select_sale()
        paths = []
        with patch("app.ui.sale_history_window.TicketPreviewDialog") as preview:
            def check_file_during_preview():
                self.assertEqual(len(paths), 1)
                self.assertTrue(paths[0].is_file())
                self.assertEqual(len(PdfReader(paths[0]).pages), 1)
                return None

            def capture_path(path, folio, parent):
                paths.append(Path(path))
                self.assertEqual(folio, self.sale["folio"])
                self.assertIs(parent, self.window)
                return preview.return_value

            preview.side_effect = capture_path
            preview.return_value.exec.side_effect = check_file_during_preview
            self.window._ver_ticket_pdf()
            preview.return_value.release_document.assert_called_once()

        self.assertEqual(len(paths), 1)
        self.assertFalse(paths[0].exists())
        self.assertTrue(self.window.ticket.isEnabled())

    def test_pdf_is_viewable_inside_qt_and_in_original_ticket_width(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.window.ticket_service.generate_sale_ticket(
                self.sale["id"], Path(directory) / "ticket.pdf"
            )
            preview = TicketPreviewDialog(path, self.sale["folio"], self.window)
            try:
                self.assertIsInstance(preview.document, QPdfDocument)
                self.assertIs(preview.pdf_view.document(), preview.document)
                self.assertGreaterEqual(preview.document.pageCount(), 1)
                self.assertAlmostEqual(
                    preview.document.pagePointSize(0).width(), 80 * 72 / 25.4,
                    delta=1.0,
                )
                self.assertTrue(preview.print_button.isEnabled())
            finally:
                preview.release_document()
                preview.close()

    def test_preview_keeps_pdf_in_memory_not_locked_on_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.window.ticket_service.generate_sale_ticket(
                self.sale["id"], Path(directory) / "ticket.pdf"
            )
            preview = TicketPreviewDialog(path, self.sale["folio"], self.window)
            try:
                # En Windows falla si QPdfDocument conserva un descriptor abierto.
                path.unlink()
                self.assertFalse(path.exists())
                self.assertEqual(preview.document.pageCount(), 1)
            finally:
                preview.release_document()
                preview.close()

    def test_printing_pdf_to_virtual_printer_without_save_dialog(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.window.ticket_service.generate_sale_ticket(
                self.sale["id"], Path(directory) / "ticket.pdf"
            )
            preview = TicketPreviewDialog(path, self.sale["folio"], self.window)
            output = Path(directory) / "virtual_printer_output.pdf"
            try:
                printer = QPrinter(QPrinter.PrinterMode.HighResolution)
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                printer.setOutputFileName(str(output))
                printer.setPageSize(
                    QPageSize(
                        preview.document.pagePointSize(0),
                        QPageSize.Unit.Point,
                    )
                )
                print_pdf_document(preview.document, printer)
                self.assertTrue(output.is_file())
                self.assertEqual(len(PdfReader(output).pages), 1)
                self.assertGreater(output.stat().st_size, 500)
            finally:
                preview.release_document()
                preview.close()


if __name__ == "__main__":
    unittest.main()
