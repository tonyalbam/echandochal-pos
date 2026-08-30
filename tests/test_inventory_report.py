import sqlite3
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from app.database.schema import create_database
from app.services.product_service import ProductService


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


class InventoryReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MemoryDatabase()
        create_database(self.database)
        self.service = ProductService(self.database)
        self._insert_products()

    def tearDown(self) -> None:
        self.database.close()

    def _insert_products(self) -> None:
        cursor = self.database.cursor()
        cursor.executemany(
            """
            INSERT INTO productos (
                codigo, nombre, costo, precio, existencia,
                stock_minimo, activo
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ("P-1", "Producto normal", 10, 20, 8, 3, 1),
                ("P-2", "Producto bajo", 25, 50, 2, 5, 1),
                ("P-3", "Producto agotado", 30, 60, 0, 4, 1),
                ("P-4", "Producto inactivo", 100, 200, 10, 2, 0),
            ),
        )
        self.database.commit()

    def test_inventory_summary_excludes_inactive_products(self) -> None:
        report = self.service.get_inventory_report()

        self.assertEqual(report["total_productos"], 3)
        self.assertEqual(report["productos_stock_bajo"], 2)
        self.assertEqual(report["valor_total_costo"], 130.0)
        self.assertEqual(report["valor_total_venta"], 260.0)

        products = {
            product["codigo"]: product
            for product in report["productos"]
        }
        self.assertEqual(products["P-2"]["faltante_minimo"], 3.0)
        self.assertEqual(products["P-2"]["estado_stock"], "BAJO")
        self.assertEqual(products["P-3"]["estado_stock"], "AGOTADO")
        self.assertNotIn("P-4", products)

    def test_inventory_report_applies_search(self) -> None:
        report = self.service.get_inventory_report("bajo")

        self.assertEqual(report["total_productos"], 1)
        self.assertEqual(report["productos"][0]["codigo"], "P-2")

    def test_export_inventory_report_contains_auditable_formulas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = self.service.export_inventory_report(
                Path(directory) / "inventario"
            )

            workbook = load_workbook(output_path, data_only=False)
            sheet = workbook["Inventario"]

            self.assertEqual(sheet["A7"].value, "P-3")
            self.assertEqual(sheet["L7"].value, "=MAX(K7-J7,0)")
            self.assertEqual(sheet["M7"].value, "=H7*J7")
            self.assertEqual(
                sheet["O7"].value,
                '=IF(J7<=0,"AGOTADO",IF(J7<=K7,"BAJO","OK"))',
            )
            self.assertEqual(sheet["B3"].value, "=COUNTA(A7:A9)")
            self.assertEqual(sheet.auto_filter.ref, "A6:O9")

            workbook.close()


if __name__ == "__main__":
    unittest.main()
