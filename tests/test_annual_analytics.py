"""Regresión de analítica anual sin modificaciones de ventas o inventario."""
import sqlite3
import unittest
from datetime import date

from app.database.schema import create_database
from app.services.dashboard_service import DashboardService


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


class AnnualAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        self.service = DashboardService(self.db)
        cursor = self.db.cursor()
        cursor.execute(
            "INSERT INTO categorias(nombre) VALUES ('Ejemplo')"
        )
        category = cursor.lastrowid
        cursor.executemany(
            """INSERT INTO productos
               (codigo, nombre, marca, categoria_id, existencia, costo,
                precio, fecha_creacion)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                ("A", "Lana azul", "Marca Uno", category, 10, 30, 70,
                 "2026-01-01"),
                ("B", "Lana roja", "Marca Dos", category, 15, 20, 90,
                 "2026-04-01"),
                ("C", "Lana sin venta", "Marca Uno", category, 6, 15, 40,
                 "2026-02-01"),
                ("D", "Producto nuevo", "Marca Tres", category, 2, 5, 20,
                 "2026-10-25"),
            ],
        )
        cursor.execute(
            """INSERT INTO ventas(
                   folio, fecha, hora, subtotal, total, metodo_pago,
                   monto_comision, total_neto)
               VALUES ('V1', '2026-01-12', '10:00:00',
                       400, 360, 'Mixto', 12, 348)"""
        )
        sale = cursor.lastrowid
        cursor.executemany(
            """INSERT INTO detalle_venta
               (venta_id, producto_id, cantidad, precio_unitario,
                costo_unitario, subtotal)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (sale, 1, 3, 70, 30, 300),
                (sale, 2, 1, 90, 20, 100),
            ],
        )
        cursor.execute(
            """INSERT INTO ventas(
                   folio, fecha, hora, subtotal, total, metodo_pago,
                   cancelada)
               VALUES ('V2', '2026-01-13', '10:00:00',
                       500, 500, 'Efectivo', 1)"""
        )
        cancelled = cursor.lastrowid
        cursor.execute(
            """INSERT INTO detalle_venta
               (venta_id, producto_id, cantidad, precio_unitario,
                costo_unitario, subtotal)
               VALUES (?, 2, 10, 50, 5, 500)""", (cancelled,)
        )
        cursor.execute(
            """INSERT INTO ventas(
                   folio, fecha, hora, subtotal, total, metodo_pago,
                   monto_comision)
               VALUES ('V3', '2026-08-15', '10:00:00',
                       60, 60, 'Efectivo', 0)"""
        )
        recent_sale = cursor.lastrowid
        cursor.execute(
            """INSERT INTO detalle_venta(
                   venta_id, producto_id, cantidad, precio_unitario,
                   costo_unitario, subtotal)
               VALUES (?, 1, 1, 60, 30, 60)""", (recent_sale,)
        )
        self.db.commit()

    def tearDown(self):
        self.db.connection.close()

    def test_correct_annual_cards(self):
        result = self.service.get_analytics_annual(2026, date(2026, 11, 2))
        self.assertEqual(result["marca_mas_vendida"]["nombre"], "Marca Uno")
        self.assertEqual(result["marca_mas_vendida"]["unidades"], 4)
        self.assertEqual(result["producto_mas_vendido"]["nombre"], "Lana azul")
        self.assertEqual(result["producto_mas_vendido"]["categoria"], "Ejemplo")
        self.assertEqual(result["producto_mas_vendido"]["unidades"], 4)
        self.assertEqual(result["producto_mas_rentable"]["nombre"], "Lana azul")
        self.assertAlmostEqual(result["producto_mas_rentable"]["utilidad"], 201)
        self.assertEqual(result["producto_menos_vendido"]["nombre"], "Lana sin venta")

    def test_revenue_donut_ignores_cancellations_and_allocates_discount(self):
        result = self.service.get_analytics_annual(2026, date(2026, 11, 2))
        leaders = result["top_productos_ingresos"]
        self.assertEqual([item["nombre"] for item in leaders],
                         ["Lana azul", "Lana roja"])
        self.assertAlmostEqual(leaders[0]["ventas"], 330)
        self.assertAlmostEqual(leaders[1]["ventas"], 90)
        self.assertAlmostEqual(sum(item["ventas"] for item in leaders), 420)
        self.assertAlmostEqual(sum(item["porcentaje"] for item in leaders), 100)

    def test_monthly_cumulative_uses_existing_profit_rules(self):
        result = self.service.get_analytics_annual(2026, date(2026, 11, 2))
        months = result["utilidad_acumulada"]
        self.assertEqual(len(months), 12)
        self.assertAlmostEqual(months[0]["utilidad"], 238)
        self.assertAlmostEqual(months[0]["acumulada"], 238)
        self.assertAlmostEqual(months[6]["acumulada"], 238)
        self.assertAlmostEqual(months[7]["acumulada"], 268)
        self.assertAlmostEqual(
            months[-1]["acumulada"], self.service.get_profit_for_period("2026")
        )

    def test_old_inventory_detection_excludes_recent_and_no_stock(self):
        result = self.service.get_analytics_annual(2026, date(2026, 11, 2))
        old = result["sin_venta_90_dias"]
        codes = {item["codigo"] for item in old}
        self.assertEqual(codes, {"B", "C"})
        empty = next(item for item in old if item["codigo"] == "C")
        self.assertIsNone(empty["ultima_venta"])
        self.assertEqual(empty["valor_inmovilizado"], 90)
        self.assertGreater(empty["dias_sin_venta"], 90)

    def test_stagnant_inventory_threshold_is_strictly_over_90_days(self):
        # El 15 de agosto + 90 días = 13 de noviembre.
        exact = self.service.get_analytics_annual(2026, date(2026, 11, 13))
        self.assertNotIn(
            "A", {row["codigo"] for row in exact["sin_venta_90_dias"]}
        )
        overdue = self.service.get_analytics_annual(2026, date(2026, 11, 14))
        self.assertIn(
            "A", {row["codigo"] for row in overdue["sin_venta_90_dias"]}
        )

    def test_analytics_does_not_modify_data(self):
        cursor = self.db.cursor()
        before = [
            [tuple(row) for row in cursor.execute(f"SELECT * FROM {table}")]
            for table in ("productos", "ventas", "detalle_venta",
                          "movimientos_inventario")
        ]
        self.service.get_analytics_annual(2026, date(2026, 11, 2))
        after = [
            [tuple(row) for row in cursor.execute(f"SELECT * FROM {table}")]
            for table in ("productos", "ventas", "detalle_venta",
                          "movimientos_inventario")
        ]
        self.assertEqual(before, after)

    def test_empty_year_has_empty_rankings_and_zero_profit(self):
        result = self.service.get_analytics_annual(2025, date(2026, 11, 2))
        self.assertIsNone(result["marca_mas_vendida"])
        self.assertIsNone(result["producto_mas_vendido"])
        self.assertEqual(result["top_productos_ingresos"], [])
        self.assertTrue(all(month["acumulada"] == 0 for month in
                            result["utilidad_acumulada"]))


if __name__ == "__main__":
    unittest.main()
