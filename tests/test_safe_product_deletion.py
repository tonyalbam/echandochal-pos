"""Regresión del borrado lógico de productos con movimientos históricos."""
import sqlite3
import unittest
from unittest.mock import patch

from app.database.schema import create_database
from app.services.product_service import ProductService
from app.services.sale_service import SaleService
from app.services.sale_history_service import SaleHistoryService
from app.services.report_service import ReportService
from app.services.cash_closing_service import CashClosingService
from app.services.dashboard_service import DashboardService
from app.services.purchase_service import PurchaseService


class MemoryDB:
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


class FixedDateTime:
    @classmethod
    def now(cls):
        from datetime import datetime
        return datetime(2026, 11, 2, 13, 0)


class DeleteProductTest(unittest.TestCase):
    def setUp(self):
        self.db = MemoryDB()
        create_database(self.db)
        self.product_service = ProductService(self.db)
        self.pid = self.product_service.create_product({
            "nombre": "Estambre histórico", "precio": 100, "costo": 30,
            "existencia": 10, "color": "Azul"
        })

    def tearDown(self):
        self.db.connection.close()

    def test_delete_preserves_sales_and_financial_reports(self):
        with patch("app.services.sale_service.datetime", FixedDateTime):
            sale = SaleService(self.db).create_sale(
                [{"producto_id": self.pid, "cantidad": 1, "precio_unitario": 100}],
                payments={"Efectivo": 100}, cash_received=100
            )
        before = (
            SaleHistoryService(self.db).get_sale(sale["id"]),
            ReportService(self.db).get_annual_financial_report(2026),
            CashClosingService(self.db).get_daily_closing("2026-11-02"),
            DashboardService(self.db).get_payment_sales_for_period("2026-11"),
        )
        self.product_service.delete_product(self.pid)
        after = (
            SaleHistoryService(self.db).get_sale(sale["id"]),
            ReportService(self.db).get_annual_financial_report(2026),
            CashClosingService(self.db).get_daily_closing("2026-11-02"),
            DashboardService(self.db).get_payment_sales_for_period("2026-11"),
        )
        self.assertEqual(before, after)
        self.assertEqual(self.product_service.list_products(include_inactive=True), [])
        code = self.product_service.get_product(self.pid)["codigo"]
        self.assertIsNone(SaleService(self.db).find_product(code))
        self.assertEqual(SaleService(self.db).search_products(code), [])
        self.assertIsNone(PurchaseService(self.db).find_product(code))
        self.assertEqual(PurchaseService(self.db).search_products(code), [])
        self.assertEqual(self.db.cursor().execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(self.db.cursor().execute("PRAGMA integrity_check").fetchone()[0], "ok")
        with self.assertRaises(ValueError):
            self.product_service.delete_product(self.pid)

    def test_deleted_products_keep_existing_codes_and_history(self):
        code = self.product_service.get_product(self.pid)["codigo"]
        self.product_service.delete_product(self.pid)
        next_id = self.product_service.create_product({
            "nombre": "Producto nuevo", "precio": 10
        })
        self.assertNotEqual(
            self.product_service.get_product(next_id)["codigo"], code
        )
        self.assertEqual(self.product_service.get_product(self.pid)["codigo"], code)

    def test_schema_migration_preserves_previous_product_rows(self):
        self.db.cursor().execute(
            "INSERT INTO auditoria (accion, modulo) VALUES ('TEST', 'PRODUCTOS')"
        )
        create_database(self.db)
        self.assertEqual(self.product_service.get_product(self.pid)["eliminado"], 0)
        self.assertEqual(len(self.product_service.list_products()), 1)


if __name__ == "__main__":
    unittest.main()
