"""Auditoría de utilidad: costos vendidos, gastos y movimientos que no son gastos."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from openpyxl import load_workbook
from pypdf import PdfReader
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget

from app.database.schema import create_database
from app.services.cash_closing_service import CashClosingService
from app.ui.cash_closing_window import CashClosingWindow


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


class ProfitBreakdownTest(unittest.TestCase):
    def setUp(self):
        self.database = MemoryDatabase()
        create_database(self.database)
        cursor = self.database.cursor()
        cursor.execute(
            """INSERT INTO productos (codigo,nombre,costo,precio,existencia)
               VALUES ('P1','Artículo con costo histórico',100,200,15)"""
        )
        self.product_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO ventas (folio, fecha, hora, subtotal, total,
                   metodo_pago, monto_comision, total_neto)
               VALUES ('V-COST-1','2026-11-05','11:10:00',1000,1000,
                       'Mercado Libre',4,996)"""
        )
        sale_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO detalle_venta
               (venta_id, producto_id, cantidad, precio_unitario,
                costo_unitario, subtotal)
               VALUES (?, ?, 5, 200, 100, 1000)""",
            (sale_id, self.product_id),
        )
        cursor.execute(
            """INSERT INTO proveedores(nombre) VALUES ('Proveedor')"""
        )
        supplier_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO compras(folio, proveedor_id, fecha, subtotal,total)
               VALUES ('C-COST-1',?,'2026-11-05',900,900)""",
            (supplier_id,),
        )
        purchase_id = cursor.lastrowid
        cursor.executemany(
            """INSERT INTO pagos_compra(compra_id, metodo_pago, monto_centavos)
               VALUES (?, ?, ?)""",
            ((purchase_id, "Efectivo", 20000),
             (purchase_id, "Tarjeta", 60000),
             (purchase_id, "Transferencia", 10000)),
        )
        cursor.execute(
            "UPDATE productos SET costo = 300 WHERE id = ?",
            (self.product_id,),
        )
        cursor.executemany(
            """INSERT INTO gastos_caja
               (fecha, tipo, descripcion, monto_centavos, anulado)
               VALUES ('2026-11-05',?,?,?,?)""",
            (
                ("Gastos Fijos", "Renta", 8000, 0),
                ("Gastos variables", "Papelería", 3000, 0),
                ("Sobre/Valores", "Sobre en resguardo", 30000, 0),
                ("Gastos Fijos", "Cancelado", 20000, 1),
            ),
        )
        self.database.commit()
        self.service = CashClosingService(self.database)

    def tearDown(self):
        self.database.connection.close()

    def test_gross_and_operating_profit_are_distinct(self):
        result = self.service.get_daily_closing("2026-11-05")
        self.assertEqual(result["total_ventas"], 1000)
        self.assertEqual(result["comisiones"], 4)
        self.assertEqual(result["dinero_neto"], 996)
        self.assertEqual(result["costo"], 500)
        self.assertEqual(result["utilidad_bruta"], 496)
        self.assertEqual(result["gastos_fijos"], 80)
        self.assertEqual(result["gastos_variables"], 30)
        self.assertEqual(result["gastos_operativos"], 110)
        self.assertEqual(result["sobre_valores"], 300)
        self.assertEqual(result["utilidad_operativa"], 386)
        self.assertEqual(result["utilidad"], 386)

    def test_purchase_900_is_not_subtracted_twice_from_profit(self):
        result = self.service.get_daily_closing("2026-11-05")
        self.assertEqual(result["utilidad"], 386)
        self.assertNotEqual(result["utilidad"], 386 - 900)

    def test_historical_cost_does_not_change_after_new_purchase(self):
        items = self.service.get_sold_cost_breakdown("2026-11-05")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["codigo"], "P1")
        self.assertEqual(items[0]["cantidad"], 5)
        self.assertEqual(items[0]["costo_unitario"], 100)
        self.assertEqual(items[0]["costo_total"], 500)
        self.assertEqual(
            sum(item["costo_total"] for item in items),
            self.service.get_daily_closing("2026-11-05")["costo"],
        )

    def test_canceled_expense_not_counted_as_profit_reduction(self):
        self.database.cursor().execute(
            "UPDATE gastos_caja SET anulado = 1 WHERE descripcion = 'Papelería'"
        )
        self.database.commit()
        self.assertEqual(
            self.service.get_daily_closing("2026-11-05")["utilidad"], 416
        )

    def test_excel_and_pdf_show_profit_breakdown(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            excel = self.service.export_excel("2026-11-05", base / "corte.xlsx")
            pdf = self.service.export_pdf("2026-11-05", base / "corte.pdf")
            book = load_workbook(excel, data_only=False)
            self.assertIn("Desglose utilidad", book.sheetnames)
            self.assertIn("Entradas salidas acumuladas", book.sheetnames)
            self.assertIn("Corte general", book.sheetnames)
            self.assertEqual(
                book["Entradas salidas acumuladas"]["A2"].value,
                "Ventas netas en efectivo",
            )
            self.assertEqual(
                book["Corte general"]["B3"].value,
                "Por conciliar",
            )
            sheet = book["Desglose utilidad"]
            self.assertEqual(sheet["B2"].value, 996)
            self.assertEqual(sheet["B3"].value, 500)
            self.assertEqual(sheet["B4"].value, 496)
            self.assertEqual(sheet["B7"].value, 386)
            self.assertEqual(sheet["E13"].value, 500)
            self.assertEqual(book["Corte diario"]["B14"].value, 386)
            book.close()
            output = "\n".join(
                p.extract_text() or "" for p in PdfReader(pdf).pages
            )
            self.assertIn("Desglose de utilidad", output)
            self.assertIn("Corte general entradas/salidas acumuladas", output)
            self.assertIn("Corte general", output)
            self.assertIn("Utilidad operativa", output)
            self.assertIn("500.00", output)
            self.assertIn("386.00", output)


class ProfitBreakdownUiTest(ProfitBreakdownTest):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_daily_profit_label_and_audit_dialog(self):
        window = CashClosingWindow(self.database)
        try:
            from PySide6.QtCore import QDate
            window.date.setDate(QDate(2026, 11, 5))
            window.show()
            self.app.processEvents()
            self.assertEqual(window.values["utilidad"].text(), "$ 386.00")
            self.assertEqual(window.profit_values["costo"].text(), "$ 500.00")
            self.assertEqual(
                window.profit_values["gastos_operativos"].text(), "$ 110.00"
            )
            dialog = window._build_cost_breakdown_dialog()
            try:
                table = dialog.findChild(QTableWidget, "cost_detail")
                self.assertIsNotNone(table)
                self.assertEqual(table.rowCount(), 1)
                self.assertEqual(table.item(0, 4).text(), "$ 500.00")
                summary = dialog.findChild(QLabel, "cost_profit_summary")
                self.assertIn("386.00", summary.text())
                self.assertIn("500.00", summary.text())
            finally:
                dialog.close()
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
