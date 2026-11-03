import sqlite3
import unittest

from app.database.schema import create_database
from app.services.product_service import ProductService
from app.services.quick_stock_service import QuickStockService
from app.services.sale_service import SaleService


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


class QuickStockServiceTest(unittest.TestCase):
    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        self.product_service = ProductService(self.db)
        self.id1 = self.product_service.create_product({
            "nombre": "Estambre Azul", "codigo_barras": "750000111",
            "codigo_qr": "QR-AZUL", "existencia": 4,
        })
        self.id2 = self.product_service.create_product({
            "nombre": "Estambre Rojo", "codigo_barras": "750000222",
            "existencia": 8,
        })
        self.stock = QuickStockService(self.db)

    def tearDown(self):
        self.db.connection.close()

    def stock_quantity(self, product_id):
        return self.product_service.get_product(product_id)["existencia"]

    def test_repeat_scanning_increments_without_writing_until_save(self):
        self.stock.add_scan("750000111")
        self.stock.add_scan("750000111")
        self.stock.add_scan("QR-AZUL")
        self.assertEqual(self.stock.pending[self.id1], 3)
        self.assertEqual(self.stock_quantity(self.id1), 4)
        self.assertEqual(self.db.cursor().execute(
            "SELECT COUNT(*) FROM movimientos_inventario"
        ).fetchone()[0], 0)
        self.assertEqual(self.stock.save(), 3)
        self.assertEqual(self.stock_quantity(self.id1), 7)
        movement = self.db.cursor().execute(
            "SELECT tipo, cantidad, existencia_anterior, existencia_nueva "
            "FROM movimientos_inventario WHERE producto_id = ?", (self.id1,)
        ).fetchone()
        self.assertEqual(tuple(movement), ("ENTRADA_RAPIDA", 3, 4, 7))

    def test_multiple_products_and_manual_quantity(self):
        self.stock.add_scan("750000111")
        self.stock.add_scan("750000222")
        self.stock.set_quantity(self.id2, 6)
        self.assertEqual(self.stock.save(), 7)
        self.assertEqual(self.stock_quantity(self.id1), 5)
        self.assertEqual(self.stock_quantity(self.id2), 14)
        self.assertEqual(self.db.cursor().execute(
            "PRAGMA integrity_check"
        ).fetchone()[0], "ok")

    def test_cancel_by_discarding_has_no_side_effects(self):
        self.stock.add_scan("750000111")
        self.assertEqual(self.stock_quantity(self.id1), 4)
        self.assertEqual(self.db.cursor().execute(
            "SELECT COUNT(*) FROM movimientos_inventario"
        ).fetchone()[0], 0)

    def test_unknown_and_deleted_product_are_rejected(self):
        with self.assertRaises(ValueError):
            self.stock.add_scan("NOT-FOUND")
        self.product_service.delete_product(self.id1)
        with self.assertRaises(ValueError):
            self.stock.add_scan("750000111")
        self.assertEqual(self.stock_quantity(self.id1), 4)

    def test_atomic_rollback_if_second_product_is_deactivated(self):
        self.stock.add_scan("750000111")
        self.stock.add_scan("750000222")
        self.product_service.deactivate_product(self.id2)
        with self.assertRaises(ValueError):
            self.stock.save()
        self.assertEqual(self.stock_quantity(self.id1), 4)
        self.assertEqual(self.stock_quantity(self.id2), 8)
        self.assertEqual(self.db.cursor().execute(
            "SELECT COUNT(*) FROM movimientos_inventario"
        ).fetchone()[0], 0)

    def test_invalid_quantities(self):
        self.stock.add_scan("750000111")
        for value in (-1, 1.5, True, 1000001):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.stock.set_quantity(self.id1, value)
        self.stock.set_quantity(self.id1, 0)
        with self.assertRaises(ValueError):
            self.stock.save()

    def test_sales_historical_records_not_modified(self):
        # Solo modifica productos.existencia y movimientos_inventario.
        self.stock.add_scan("750000111")
        before = [tuple(row) for row in self.db.cursor().execute(
            "SELECT * FROM ventas"
        )]
        self.stock.save()
        after = [tuple(row) for row in self.db.cursor().execute(
            "SELECT * FROM ventas"
        )]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
