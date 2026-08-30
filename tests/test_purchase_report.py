import sqlite3
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from app.database.schema import create_database
from app.services.purchase_service import PurchaseService


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


class PurchaseReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MemoryDatabase()
        create_database(self.database)
        self._insert_data()
        self.service = PurchaseService(self.database)

    def tearDown(self) -> None:
        self.database.close()

    def _insert_data(self) -> None:
        cursor = self.database.cursor()
        cursor.executemany(
            "INSERT INTO proveedores (nombre) VALUES (?)",
            (("Proveedor Uno",), ("Proveedor Dos",)),
        )
        cursor.execute(
            """
            INSERT INTO productos (
                codigo, nombre, costo, precio, existencia
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("P-1", "Producto prueba", 20, 40, 10),
        )
        product_id = int(cursor.lastrowid)

        purchases = (
            ("C-20260810-0001", 1, "2026-08-10", 100, "Primera compra"),
            ("C-20260910-0001", 2, "2026-09-10", 200, "Segunda compra"),
        )
        for folio, supplier_id, purchase_date, total, notes in purchases:
            cursor.execute(
                """
                INSERT INTO compras (
                    folio, proveedor_id, fecha, subtotal, total, notas
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (folio, supplier_id, purchase_date, total, total, notes),
            )
            purchase_id = int(cursor.lastrowid)
            cursor.execute(
                """
                INSERT INTO detalle_compra (
                    compra_id, producto_id, cantidad, costo_unitario,
                    subtotal
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (purchase_id, product_id, total / 20, 20, total),
            )

        self.database.commit()

    def test_list_purchases_filters_period_and_supplier(self) -> None:
        purchases = self.service.list_purchases(
            supplier_id=1,
            date_from="2026-08-01",
            date_to="2026-08-31",
        )

        self.assertEqual(len(purchases), 1)
        self.assertEqual(purchases[0]["folio"], "C-20260810-0001")
        self.assertEqual(purchases[0]["proveedor"], "Proveedor Uno")

    def test_search_matches_supplier_and_notes(self) -> None:
        by_supplier = self.service.list_purchases("Proveedor Dos")
        by_notes = self.service.list_purchases("Primera compra")

        self.assertEqual(by_supplier[0]["folio"], "C-20260910-0001")
        self.assertEqual(by_notes[0]["folio"], "C-20260810-0001")

    def test_export_purchase_report_respects_filters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = self.service.export_purchases_report(
                Path(directory) / "compras",
                supplier_id=1,
                date_from="2026-08-01",
                date_to="2026-08-31",
            )

            workbook = load_workbook(output_path, data_only=False)
            purchases_sheet = workbook["Compras"]
            items_sheet = workbook["Productos comprados"]

            self.assertEqual(
                purchases_sheet["A6"].value,
                "C-20260810-0001",
            )
            self.assertEqual(purchases_sheet["C6"].value, "Proveedor Uno")
            self.assertEqual(purchases_sheet["E6"].value, 100)
            self.assertEqual(purchases_sheet["E7"].value, "=SUM(E6:E6)")
            self.assertEqual(items_sheet["D2"].value, "P-1")
            self.assertEqual(items_sheet["H2"].value, 100)
            self.assertIsNone(purchases_sheet["A7"].value)

            workbook.close()

    def test_export_rejects_inverted_period(self) -> None:
        with self.assertRaises(ValueError):
            self.service.export_purchases_report(
                "compras.xlsx",
                date_from="2026-09-01",
                date_to="2026-08-01",
            )


if __name__ == "__main__":
    unittest.main()
