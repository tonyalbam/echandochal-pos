import sqlite3
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from app.database.schema import create_database
from app.services.dashboard_service import DashboardService
from app.services.report_service import ReportService


class MemoryDatabase:
    """Conexión SQLite en memoria para pruebas."""

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


class AnnualFinancialReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MemoryDatabase()
        create_database(self.database)
        self._insert_test_data()

    def tearDown(self) -> None:
        self.database.close()

    def _insert_test_data(self) -> None:
        cursor = self.database.cursor()

        cursor.execute(
            """
            INSERT INTO productos (
                codigo,
                nombre,
                costo,
                precio,
                existencia
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            ("PRUEBA-1", "Producto de prueba", 50, 85, 10),
        )
        product_id = int(cursor.lastrowid)

        cursor.execute(
            """
            INSERT INTO ventas (
                folio,
                fecha,
                hora,
                subtotal,
                total,
                metodo_pago,
                porcentaje_comision,
                monto_comision,
                total_neto
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "V-20260830-0001",
                "2026-08-30",
                "12:00:00",
                85,
                85,
                "Mercado Libre",
                4,
                3.40,
                81.60,
            ),
        )
        sale_id = int(cursor.lastrowid)

        cursor.execute(
            """
            INSERT INTO detalle_venta (
                venta_id,
                producto_id,
                cantidad,
                precio_unitario,
                costo_unitario,
                subtotal
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sale_id, product_id, 1, 85, 50, 85),
        )

        cursor.execute(
            """
            INSERT INTO ventas (
                folio,
                fecha,
                hora,
                subtotal,
                total,
                metodo_pago,
                total_neto,
                cancelada
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "V-20260901-0001",
                "2026-09-01",
                "12:00:00",
                100,
                100,
                "Efectivo",
                100,
                1,
            ),
        )
        cancelled_sale_id = int(cursor.lastrowid)

        cursor.execute(
            """
            INSERT INTO detalle_venta (
                venta_id,
                producto_id,
                cantidad,
                precio_unitario,
                costo_unitario,
                subtotal
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cancelled_sale_id,
                product_id,
                1,
                100,
                50,
                100,
            ),
        )

        self.database.commit()

    def test_annual_report_uses_historical_cost(self) -> None:
        report = ReportService(
            self.database
        ).get_annual_financial_report(2026)

        self.assertEqual(report["year"], 2026)
        self.assertEqual(report["ventas"], 85.0)
        self.assertEqual(report["costo"], 50.0)
        self.assertEqual(report["comisiones"], 3.4)
        self.assertEqual(report["ingreso_neto"], 81.6)
        self.assertEqual(report["utilidad"], 31.6)
        self.assertEqual(len(report["mensual"]), 12)

        august = report["mensual"][7]
        september = report["mensual"][8]

        self.assertEqual(
            august,
            {
                "mes": 8,
                "ventas": 85.0,
                "comisiones": 3.4,
                "costo": 50.0,
                "ingreso_neto": 81.6,
                "utilidad": 31.6,
            },
        )
        self.assertEqual(september["ventas"], 0.0)
        self.assertEqual(september["utilidad"], 0.0)

    def test_dashboard_reuses_annual_report_months(self) -> None:
        report_service = ReportService(self.database)
        dashboard_service = DashboardService(self.database)

        self.assertEqual(
            dashboard_service.get_monthly_financial_summary(
                2026
            ),
            report_service.get_annual_financial_report(
                2026
            )["mensual"],
        )

    def test_export_annual_report_to_excel(self) -> None:
        service = ReportService(self.database)

        with tempfile.TemporaryDirectory() as directory:
            output_path = service.export_annual_financial_report(
                2026,
                Path(directory) / "reporte_2026",
            )

            self.assertEqual(output_path.suffix, ".xlsx")
            self.assertTrue(output_path.exists())

            workbook = load_workbook(
                output_path,
                data_only=False,
            )
            sheet = workbook["Reporte anual"]

            self.assertEqual(
                sheet["A1"].value,
                "Echando Chal POS - Reporte financiero 2026",
            )
            self.assertEqual(sheet["A14"].value, "Agosto")
            self.assertEqual(sheet["B14"].value, 85.0)
            self.assertEqual(sheet["C14"].value, 50.0)
            self.assertEqual(sheet["D14"].value, 3.4)
            self.assertEqual(sheet["E14"].value, 81.6)
            self.assertEqual(sheet["F14"].value, 31.6)
            self.assertEqual(sheet["B19"].value, 85.0)
            self.assertEqual(sheet.auto_filter.ref, "A6:F18")

            workbook.close()


if __name__ == "__main__":
    unittest.main()
