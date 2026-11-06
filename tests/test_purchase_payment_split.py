"""Compra con pagos mixtos y conciliación de caja sin duplicar costos."""
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from app.database.schema import create_database
from app.services.purchase_service import PurchaseService
from app.services.petty_cash_service import PettyCashService
from app.services.cash_closing_service import CashClosingService
from app.services.cash_closing_history_service import CashClosingHistoryService


class Db:
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


class PurchasePaymentTest(unittest.TestCase):
    def setUp(self):
        self.db = Db()
        create_database(self.db)
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO proveedores(nombre) VALUES('Proveedor')")
        self.supplier_id = cursor.lastrowid
        cursor.execute(
            """INSERT INTO productos(codigo,nombre,costo,precio,existencia)
               VALUES ('PROD-1','Mercancía',100,150,3)"""
        )
        self.product_id = cursor.lastrowid
        self.db.commit()
        self.purchases = PurchaseService(self.db)
        self.cash = PettyCashService(self.db)
        self.today = date.today().isoformat()

    def tearDown(self):
        self.db.connection.close()

    def buy(self, payments=None, unit_cost=100):
        kwargs = {
            "items": [{
                "producto_id": self.product_id,
                "cantidad": 1, "costo_unitario": unit_cost,
            }],
            "supplier_id": self.supplier_id,
        }
        if payments is not None:
            kwargs["payments"] = payments
        return self.purchases.create_purchase(**kwargs)

    def stock(self):
        return self.db.cursor().execute(
            "SELECT existencia FROM productos WHERE id = ?",
            (self.product_id,),
        ).fetchone()[0]

    def test_mixed_cash_card_transfer_atomic_and_visible_in_history(self):
        self.cash.register_initial_fund(self.today, 200)
        result = self.buy({
            "Efectivo": 40, "Tarjeta": 35.50, "Transferencia": 24.50
        })
        self.assertEqual(result["pagos"]["Efectivo"], 40)
        self.assertEqual(self.stock(), 4)
        detail = self.purchases.get_purchase(result["id"])
        self.assertEqual(
            [(p["metodo_pago"], p["monto"]) for p in detail["pagos"]],
            [("Efectivo", 40), ("Tarjeta", 35.5), ("Transferencia", 24.5)],
        )
        listed = self.purchases.list_purchases()
        self.assertEqual(len(listed), 1)
        for method in PurchaseService.PAYMENT_METHODS:
            self.assertIn(method, listed[0]["formas_pago"])
        summary = self.cash.get_summary(self.today)
        self.assertEqual(summary["compras_efectivo_centavos"], 4000)
        self.assertEqual(summary["saldo_esperado_centavos"], 16000)
        flows = {
            x["metodo_pago"]: x for x in self.cash.get_payment_flows(self.today)
        }
        self.assertEqual(flows["Efectivo"]["compras_centavos"], 4000)
        self.assertEqual(flows["Tarjeta"]["compras_centavos"], 3550)
        self.assertEqual(flows["Transferencia"]["compras_centavos"], 2450)
        self.assertEqual(flows["Tarjeta"]["flujo_neto_centavos"], -3550)

    def test_payment_must_add_to_total_exactly_without_inventory_changes(self):
        for values in (
            {"Efectivo": 90}, {"Efectivo": 110},
            {"Efectivo": -1, "Tarjeta": 101},
            {"Tarjeta": 100.001}, {"Otro": 100},
        ):
            with self.subTest(payments=values):
                with self.assertRaises(ValueError):
                    self.buy(values)
        self.assertEqual(self.stock(), 3)
        self.assertEqual(
            self.db.cursor().execute("SELECT COUNT(*) FROM compras").fetchone()[0],
            0,
        )

    def test_cash_exceeding_available_is_rejected_atomically(self):
        self.cash.register_initial_fund(self.today, 30)
        with self.assertRaisesRegex(ValueError, "suficiente efectivo"):
            self.buy({"Efectivo": 40, "Tarjeta": 60})
        self.assertEqual(self.stock(), 3)
        self.assertEqual(self.cash.get_summary(self.today)["compras_efectivo_centavos"], 0)
        self.assertEqual(
            self.db.cursor().execute("SELECT COUNT(*) FROM pagos_compra").fetchone()[0],
            0,
        )

    def test_cash_purchase_reduces_close_and_carries_next_day(self):
        self.cash.register_initial_fund(self.today, 200)
        self.buy({"Efectivo": 60, "Tarjeta": 40})
        self.cash.add_expense(
            self.today, "Gastos variables", "Papelería", 10
        )
        closing = CashClosingService(self.db).calculate_cash_reconciliation(
            self.today, {("Billete", 100.0): 1,
                         ("Billete", 20.0): 1}, 10
        )
        self.assertEqual(closing["compras_efectivo"], 60)
        self.assertEqual(closing["efectivo_esperado"], 130)
        self.assertEqual(closing["estado"], "CUADRA")
        self.cash.confirm_closing(
            self.today, {("Billete", 100.0): 1,
                         ("Billete", 20.0): 1}, 10
        )
        snapshot = self.cash.get_closing(self.today)
        self.assertEqual(snapshot["compras_efectivo_centavos"], 6000)
        archived = CashClosingHistoryService(self.db).get_day_detail(self.today)
        self.assertEqual(archived["compras_efectivo_centavos"], 6000)
        self.assertEqual(archived["saldo_contado_centavos"], 13000)

    def test_paymented_purchase_blocked_after_daily_cash_close(self):
        self.cash.register_initial_fund(self.today, 100)
        self.cash.confirm_closing(self.today, {("Billete", 100.0): 1}, 0)
        with self.assertRaisesRegex(ValueError, "corte diario"):
            self.buy({"Tarjeta": 100})
        self.assertEqual(self.stock(), 3)

    def test_old_purchases_still_visible_without_invented_payment(self):
        result = self.buy()
        detail = self.purchases.get_purchase(result["id"])
        self.assertEqual(detail["pagos"], [])
        self.assertEqual(
            self.purchases.list_purchases()[0]["formas_pago"],
            "Sin desglose",
        )
        self.assertEqual(
            self.cash.get_summary(self.today)["compras_efectivo_centavos"], 0
        )

    def test_excel_includes_purchase_methods_and_exact_amounts(self):
        self.cash.register_initial_fund(self.today, 200)
        self.buy({"Efectivo": 10, "Tarjeta": 20, "Transferencia": 70})
        with tempfile.TemporaryDirectory() as directory:
            path = self.purchases.export_purchases_report(
                Path(directory) / "compras.xlsx"
            )
            wb = load_workbook(path)
            self.assertIn("Pagos de compras", wb.sheetnames)
            sheet = wb["Pagos de compras"]
            self.assertEqual(sheet["D2"].value, "Efectivo")
            self.assertEqual(sheet["E2"].value, 10)
            self.assertEqual(sheet["D3"].value, "Tarjeta")
            self.assertEqual(sheet["E3"].value, 20)
            self.assertEqual(sheet["D4"].value, "Transferencia")
            self.assertEqual(sheet["E4"].value, 70)
            self.assertIn("Tarjeta", wb["Compras"]["H6"].value)
            wb.close()

    def test_cash_and_card_flows_include_sales_without_double_counting_inventory(self):
        self.cash.register_initial_fund(self.today, 200)
        self.buy({"Efectivo": 30, "Tarjeta": 70})
        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO ventas(folio,fecha,hora,subtotal,total,
               metodo_pago,monto_comision,total_neto)
               VALUES('TEST-PAY', ?, '12:00:00', 150, 150, 'Mixto', 4, 146)""",
            (self.today,),
        )
        sale_id = cursor.lastrowid
        cursor.executemany(
            """INSERT INTO pagos_venta
               (venta_id, metodo_pago, monto, monto_comision)
               VALUES (?, ?, ?, ?)""",
            ((sale_id, "Efectivo", 50, 0),
             (sale_id, "Mercado Libre", 100, 4)),
        )
        self.db.commit()
        flows = {
            f["metodo_pago"]: f for f in self.cash.get_payment_flows(self.today)
        }
        self.assertEqual(flows["Efectivo"]["flujo_neto_centavos"], 2000)
        self.assertEqual(flows["Tarjeta"]["flujo_neto_centavos"], 2600)
        self.assertEqual(
            self.cash.get_summary(self.today)["saldo_esperado_centavos"], 22000
        )
        # La adquisición se contabilizó en inventario, no como gasto operativo.
        self.assertEqual(
            self.cash.get_summary(self.today)["gastos_centavos"], 0
        )

    def test_new_schema_preserves_payment_entries_after_reopen(self):
        self.cash.register_initial_fund(self.today, 200)
        self.buy({"Efectivo": 80, "Transferencia": 20})
        create_database(self.db)
        self.assertEqual(self.cash.get_summary(self.today)["compras_efectivo_centavos"], 8000)
        self.assertEqual(
            self.db.cursor().execute("PRAGMA integrity_check").fetchone()[0],
            "ok",
        )


if __name__ == "__main__":
    unittest.main()
