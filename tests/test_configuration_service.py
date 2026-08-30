import sqlite3
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from app.database.schema import create_database
from app.services.configuration_service import ConfigurationService
from app.services.report_service import ReportService
from app.services.sale_service import SaleService


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


class ConfigurationServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MemoryDatabase()
        create_database(self.database)
        self.service = ConfigurationService(self.database)

    def tearDown(self) -> None:
        self.database.close()

    def test_update_settings_persists_values(self) -> None:
        result = self.service.update_settings(
            "Mi Negocio",
            7.25,
        )

        self.assertEqual(result["nombre_negocio"], "Mi Negocio")
        self.assertEqual(result["comision_mercado_libre"], 7.25)
        self.assertEqual(
            SaleService(self.database).get_commission_rate(),
            7.25,
        )

    def test_invalid_settings_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.service.update_settings("", 4)

        with self.assertRaises(ValueError):
            self.service.update_settings("Mi Negocio", 101)

        self.assertEqual(
            self.service.get_settings()["nombre_negocio"],
            "Echando Chal",
        )

    def test_business_name_is_used_in_exported_reports(self) -> None:
        self.service.update_settings("Boutique Prueba", 4)

        with tempfile.TemporaryDirectory() as directory:
            output_path = ReportService(
                self.database
            ).export_annual_financial_report(
                2026,
                Path(directory) / "reporte.xlsx",
            )

            workbook = load_workbook(output_path, data_only=False)
            sheet = workbook["Reporte anual"]
            self.assertEqual(
                sheet["A1"].value,
                "Boutique Prueba POS - Reporte financiero 2026",
            )
            workbook.close()


if __name__ == "__main__":
    unittest.main()
