import sqlite3
import unittest

from app.database.schema import create_database
from app.services.purchase_service import PurchaseService


class MemoryDatabase:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def cursor(self):
        return self.connection.cursor()

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


class PurchaseServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MemoryDatabase()
        create_database(self.database)
        cursor = self.database.cursor()
        cursor.execute(
            "INSERT INTO proveedores (nombre) VALUES ('Proveedor Uno')"
        )
        self.supplier_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO productos (
                codigo, codigo_barras, nombre, marca, color, costo, precio,
                existencia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("EST-01", "75010001", "Estambre Abuelita", "Abuelita", "Rojo", 20, 40, 5),
        )
        self.product_id = int(cursor.lastrowid)
        self.database.commit()
        self.service = PurchaseService(self.database)

    def tearDown(self) -> None:
        self.database.close()

    def test_search_matches_code_barcode_name_and_brand(self) -> None:
        for query in ("EST", "750100", "Estambre", "Abuelita"):
            products = self.service.search_products(query)
            self.assertEqual(products[0]["codigo"], "EST-01")
            self.assertEqual(products[0]["color"], "Rojo")

    def test_purchase_requires_an_active_supplier(self) -> None:
        items = [{
            "producto_id": self.product_id,
            "cantidad": 1,
            "costo_unitario": 20,
        }]
        with self.assertRaisesRegex(ValueError, "seleccionar un proveedor"):
            self.service.create_purchase(items, supplier_id=None)

    def test_purchase_rejects_decimal_quantity(self) -> None:
        items = [{
            "producto_id": self.product_id,
            "cantidad": 1.5,
            "costo_unitario": 20,
        }]
        with self.assertRaisesRegex(ValueError, "número entero"):
            self.service.create_purchase(items, supplier_id=self.supplier_id)

    def test_purchase_with_integer_quantity_updates_inventory(self) -> None:
        items = [{
            "producto_id": self.product_id,
            "cantidad": 3,
            "costo_unitario": 22,
        }]
        result = self.service.create_purchase(
            items, supplier_id=self.supplier_id
        )
        self.assertEqual(result["total"], 66)
        stock = self.database.cursor().execute(
            "SELECT existencia FROM productos WHERE id = ?",
            (self.product_id,),
        ).fetchone()["existencia"]
        self.assertEqual(stock, 8)


if __name__ == "__main__":
    unittest.main()
