import sqlite3
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from app.database.schema import create_database
from app.services.sale_history_service import SaleHistoryService


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


class SaleHistoryExportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MemoryDatabase()
        create_database(self.database)
        self._insert_data()
        self.service = SaleHistoryService(self.database)

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
            ("P-1", "Producto uno", 50, 85, 10),
        )
        product_id = int(cursor.lastrowid)

        sales = (
            (
                "V-20260830-0001", "2026-08-30", 85, 3.4,
                81.6, 0,
            ),
            (
                "V-20260901-0001", "2026-09-01", 100, 0,
                100, 1,
            ),
        )
        for folio, sale_date, total, commission, net, cancelled in sales:
            cursor.execute(
                """
                INSERT INTO ventas (
                    folio, fecha, hora, subtotal, total, metodo_pago,
                    porcentaje_comision, monto_comision, total_neto,
                    cancelada
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    folio, sale_date, "12:00:00", total, total,
                    "Mercado Libre" if commission else "Efectivo",
                    4 if commission else 0, commission, net, cancelled,
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
                (sale_id, product_id, 1, total, 50, total),
            )

        self.database.commit()

    def test_list_sales_filters_date_range(self) -> None:
        sales = self.service.list_sales(
            date_from="2026-08-01",
            date_to="2026-08-31",
        )

        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0]["folio"], "V-20260830-0001")

    def test_export_sales_report_respects_filters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = self.service.export_sales_report(
                Path(directory) / "detalle_ventas",
                include_cancelled=False,
                date_from="2026-08-01",
                date_to="2026-08-31",
            )

            workbook = load_workbook(output_path, data_only=False)
            sales_sheet = workbook["Ventas"]
            items_sheet = workbook["Productos vendidos"]

            self.assertEqual(sales_sheet["A6"].value, "V-20260830-0001")
            self.assertEqual(sales_sheet["G6"].value, 85)
            self.assertEqual(sales_sheet["J6"].value, 81.6)
            self.assertEqual(sales_sheet["K6"].value, "ACTIVA")
            self.assertEqual(sales_sheet["G7"].value, "=SUM(G6:G6)")
            self.assertEqual(items_sheet["C2"].value, "P-1")
            self.assertEqual(items_sheet["G2"].value, 50)
            self.assertEqual(sales_sheet["D7"].value, "Totales")

            workbook.close()

    def test_export_rejects_inverted_date_range(self) -> None:
        with self.assertRaises(ValueError):
            self.service.export_sales_report(
                "reporte.xlsx",
                date_from="2026-09-01",
                date_to="2026-08-01",
            )


if __name__ == "__main__":
    unittest.main()
