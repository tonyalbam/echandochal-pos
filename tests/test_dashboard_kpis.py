import sqlite3
import unittest

from app.database.schema import create_database
from app.services.dashboard_service import DashboardService


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


class DashboardKpiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MemoryDatabase()
        create_database(self.database)
        self._insert_data()
        self.service = DashboardService(self.database)

    def tearDown(self) -> None:
        self.database.close()

    def _insert_data(self) -> None:
        cursor = self.database.cursor()
        products = (
            ("P-1", "Producto líder", 50, 85),
            ("P-2", "Producto secundario", 10, 30),
        )
        product_ids = []
        for code, name, cost, price in products:
            cursor.execute(
                """
                INSERT INTO productos (
                    codigo, nombre, costo, precio, existencia
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (code, name, cost, price, 20),
            )
            product_ids.append(int(cursor.lastrowid))

        cursor.execute(
            """
            INSERT INTO ventas (
                folio, fecha, hora, subtotal, total, metodo_pago,
                porcentaje_comision, monto_comision, total_neto
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "V-20260830-0001", "2026-08-30", "12:00:00",
                285, 285, "Mercado Libre", 4, 11.4, 273.6,
            ),
        )
        sale_id = int(cursor.lastrowid)
        cursor.executemany(
            """
            INSERT INTO detalle_venta (
                venta_id, producto_id, cantidad, precio_unitario,
                costo_unitario, subtotal
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (sale_id, product_ids[0], 3, 85, 50, 255),
                (sale_id, product_ids[1], 1, 30, 10, 30),
            ),
        )

        cursor.execute(
            """
            INSERT INTO ventas (
                folio, fecha, hora, subtotal, total, metodo_pago,
                total_neto, cancelada
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "V-20260830-0002", "2026-08-30", "13:00:00",
                500, 500, "Efectivo", 500, 1,
            ),
        )
        cancelled_sale_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO detalle_venta (
                venta_id, producto_id, cantidad, precio_unitario,
                costo_unitario, subtotal
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (cancelled_sale_id, product_ids[1], 10, 50, 10, 500),
        )
        self.database.commit()

    def test_operational_kpis_exclude_cancelled_sales(self) -> None:
        self.assertEqual(
            self.service.get_units_sold_for_period("2026-08"),
            4.0,
        )

        top_product = self.service.get_top_selling_product_for_period(
            "2026-08"
        )
        self.assertIsNotNone(top_product)
        self.assertEqual(top_product["nombre"], "Producto líder")
        self.assertEqual(top_product["cantidad"], 3.0)

    def test_profit_margin_uses_historical_cost_and_commission(self) -> None:
        self.assertEqual(
            self.service.get_profit_for_period("2026-08"),
            113.6,
        )
        self.assertEqual(
            self.service.get_profit_margin_for_period("2026-08"),
            39.86,
        )

    def test_empty_period_returns_zero_kpis(self) -> None:
        self.assertEqual(
            self.service.get_profit_margin_for_period("2025-01"),
            0.0,
        )
        self.assertEqual(
            self.service.get_units_sold_for_period("2025-01"),
            0.0,
        )
        self.assertIsNone(
            self.service.get_top_selling_product_for_period("2025-01")
        )


if __name__ == "__main__":
    unittest.main()
