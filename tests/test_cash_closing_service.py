import sqlite3
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

from app.database.schema import create_database
from app.services.cash_closing_service import CashClosingService


class MemoryDatabase:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def cursor(self) -> sqlite3.Cursor:
        return self.connection.cursor()

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


class CashClosingServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MemoryDatabase()
        create_database(self.database)
        self._insert_data()
        self.service = CashClosingService(self.database)

    def tearDown(self) -> None:
        self.database.close()

    def _insert_data(self) -> None:
        cursor = self.database.cursor()
        cursor.execute(
            """
            INSERT INTO productos (
                codigo, nombre, costo, precio, existencia
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("P-1", "Producto", 50, 100, 20),
        )
        product_id = int(cursor.lastrowid)

        sales = (
            ("V-1", "Efectivo", 100, 0, 100, 1, 50, 0),
            ("V-2", "Transferencia", 200, 0, 200, 2, 40, 0),
            ("V-3", "Mercado Libre", 300, 12, 288, 3, 50, 0),
            ("V-4", "Efectivo", 1000, 0, 1000, 10, 50, 1),
        )
        for folio, method, total, commission, net, quantity, cost, cancelled in sales:
            cursor.execute(
                """
                INSERT INTO ventas (
                    folio, fecha, hora, subtotal, total, metodo_pago,
                    porcentaje_comision, monto_comision, total_neto,
                    cancelada
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    folio, "2026-08-30", "12:00:00", total, total,
                    method, 4 if commission else 0, commission, net, cancelled,
                ),
            )
            sale_id = int(cursor.lastrowid)
            cursor.execute(
                """
                INSERT INTO detalle_venta (
                    venta_id, producto_id, cantidad, precio_unitario,
                    costo_unitario, subtotal
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (sale_id, product_id, quantity, total / quantity, cost, total),
            )
        self.database.commit()

    def test_daily_closing_calculates_required_metrics(self) -> None:
        closing = self.service.get_daily_closing("2026-08-30")

        self.assertEqual(closing["total_ventas"], 600.0)
        self.assertEqual(closing["comisiones"], 12.0)
        self.assertEqual(closing["dinero_neto"], 588.0)
        self.assertEqual(closing["numero_tickets"], 3)
        self.assertEqual(closing["productos_vendidos"], 6.0)
        self.assertEqual(closing["costo"], 280.0)
        self.assertEqual(closing["utilidad"], 308.0)

        payments = {
            row["metodo_pago"]: row
            for row in closing["formas_pago"]
        }
        self.assertEqual(payments["Efectivo"]["ventas"], 100.0)
        self.assertEqual(payments["Transferencia"]["ventas"], 200.0)
        self.assertEqual(payments["Mercado Libre"]["ventas"], 300.0)

    def test_empty_date_returns_zero_values(self) -> None:
        closing = self.service.get_daily_closing("2025-01-01")
        self.assertEqual(closing["total_ventas"], 0.0)
        self.assertEqual(closing["numero_tickets"], 0)
        self.assertEqual(closing["productos_vendidos"], 0.0)

    def test_exports_excel_and_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            excel_path = self.service.export_excel(
                "2026-08-30", Path(directory) / "corte.xlsx"
            )
            pdf_path = self.service.export_pdf(
                "2026-08-30", Path(directory) / "corte.pdf"
            )

            workbook = load_workbook(excel_path, data_only=False)
            sheet = workbook["Corte diario"]
            self.assertEqual(sheet["A4"].value, "Efectivo")
            self.assertEqual(sheet["C4"].value, 100.0)
            self.assertEqual(sheet["B9"].value, 600.0)
            self.assertEqual(sheet["B14"].value, 308.0)
            workbook.close()

            reader = PdfReader(pdf_path)
            self.assertGreaterEqual(len(reader.pages), 1)
            text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
            self.assertIn("Corte diario - 2026-08-30", text)
            self.assertIn("TOTAL VENTAS", text)
            self.assertIn("$600.00", text)
            self.assertIn("Utilidad del día", text)
            self.assertIn("Arqueo manual de efectivo", text)


if __name__ == "__main__":
    unittest.main()
