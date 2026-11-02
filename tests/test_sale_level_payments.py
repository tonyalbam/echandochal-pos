import sqlite3
import unittest
from unittest.mock import patch

from app.database.schema import create_database
from app.services.sale_service import SaleService
from app.services.sale_history_service import SaleHistoryService
from app.services.dashboard_service import DashboardService
from app.services.cash_closing_service import CashClosingService
from app.services.report_service import ReportService


class TestDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        create_database(self)
        self.cursor().execute(
            "INSERT INTO productos (codigo, nombre, precio, costo, existencia) VALUES (?, ?, ?, ?, ?)",
            ("NEW-1", "Producto prueba", 350, 200, 10),
        )
        self.commit()

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()


class FakeDateTime:
    @classmethod
    def now(cls):
        from datetime import datetime
        return datetime(2026, 11, 2, 12, 0)


class SaleLevelPaymentTest(unittest.TestCase):
    def setUp(self):
        self.db = TestDatabase()

    def tearDown(self):
        self.db.connection.close()

    def test_new_mixed_sale_and_reporting(self):
        with patch("app.services.sale_service.datetime", FakeDateTime):
            sale = SaleService(self.db).create_sale(
                [{"producto_id": 1, "cantidad": 1, "precio_unitario": 350}],
                payments={"Efectivo": 50, "Transferencia": 100, "Mercado Libre": 200},
                cash_received=100,
            )
        self.assertEqual(sale["total"], 350)
        self.assertEqual(sale["metodo_pago"], "Mixto")
        self.assertEqual(sale["change"], 50)
        self.assertEqual(sale["monto_comision"], 8)
        self.assertEqual(sale["total_neto"], 342)
        self.assertEqual(self.db.cursor().execute(
            "SELECT COUNT(*) FROM pagos_venta WHERE venta_id=?", (sale["id"],)
        ).fetchone()[0], 3)
        result = SaleHistoryService(self.db).get_sale(sale["id"])
        self.assertEqual(sum(p["monto"] for p in result["payments"]), 350)
        self.assertEqual(result["items"][0]["metodo_pago"], "Por venta")
        dashboard = DashboardService(self.db).get_payment_sales_for_period("2026-11")
        self.assertEqual(dashboard, {
            "Efectivo": 50, "Transferencia": 100, "Mercado Libre": 200
        })
        closing = CashClosingService(self.db).get_daily_closing("2026-11-02")
        self.assertEqual([p["ventas"] for p in closing["formas_pago"]], [50, 100, 200])
        annual = ReportService(self.db).get_annual_financial_report(2026)
        self.assertEqual([p["ventas"] for p in annual["formas_pago"]], [50, 100, 200])
        self.assertEqual(annual["comisiones"], 8)

    def test_invalid_payment_does_not_create_sale(self):
        with self.assertRaises(ValueError):
            SaleService(self.db).create_sale(
                [{"producto_id": 1, "cantidad": 1, "precio_unitario": 350}],
                payments={"Efectivo": 50, "Transferencia": 100},
                cash_received=50,
            )
        self.assertEqual(self.db.cursor().execute("SELECT COUNT(*) FROM ventas").fetchone()[0], 0)
        self.assertEqual(self.db.cursor().execute("SELECT existencia FROM productos").fetchone()[0], 10)


if __name__ == "__main__":
    unittest.main()
