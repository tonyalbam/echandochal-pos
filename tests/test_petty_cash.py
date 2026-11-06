"""Caja chica: cierre confirmado, gastos, arrastre y cambio de ventas mixtas."""
import sqlite3
import unittest
from unittest.mock import patch
from datetime import date

from app.database.schema import create_database
from app.services.petty_cash_service import PettyCashService
from app.services.cash_closing_service import CashClosingService
from app.services.sale_service import SaleService
from app.services.sale_history_service import SaleHistoryService


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


class PettyCashTest(unittest.TestCase):
    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        self.service = PettyCashService(self.db)

    def tearDown(self):
        self.db.connection.close()

    def add_sale(self, day, total, cash, cancelled=0):
        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO ventas
               (folio, fecha, hora, subtotal, total, metodo_pago,
                monto_comision, total_neto, cancelada)
               VALUES (?, ?, '10:00:00', ?, ?, 'Mixto', 0, ?, ?)""",
            (f"T-{day}-{cursor.execute('SELECT COUNT(*) FROM ventas').fetchone()[0]}",
             day, total, total, total, cancelled),
        )
        sale_id = cursor.lastrowid
        if cash:
            cursor.execute(
                """INSERT INTO pagos_venta (venta_id, metodo_pago, monto)
                   VALUES (?, 'Efectivo', ?)""", (sale_id, cash)
            )
        if total != cash:
            cursor.execute(
                """INSERT INTO pagos_venta (venta_id, metodo_pago, monto)
                   VALUES (?, 'Transferencia', ?)""",
                (sale_id, total - cash),
            )
        self.db.commit()

    def test_cash_sale_net_of_change_and_mixed_payments(self):
        # Cobro de $100, $50 efectivo y $50 transferencia.
        # El cliente dio $100 y recibió $50 de cambio. Caja: +$50.
        self.add_sale("2026-10-01", 100, 50)
        self.add_sale("2026-10-01", 70, 70)
        self.add_sale("2026-10-01", 800, 800, cancelled=1)
        summary = self.service.get_summary("2026-10-01")
        self.assertEqual(summary["ventas_efectivo_centavos"], 12000)
        self.assertEqual(summary["saldo_esperado_centavos"], 12000)
        cash = CashClosingService(self.db).calculate_cash_reconciliation(
            "2026-10-01", {("Billete", 100.0): 1, ("Billete", 20.0): 1}, 0
        )
        self.assertEqual(cash["estado"], "CUADRA")
        self.assertEqual(cash["ventas_efectivo"], 120)

    def test_expenses_reduce_expected_cash_and_roll_to_next_day(self):
        self.add_sale("2026-10-01", 250, 250)
        self.service.add_expense("2026-10-01", "Gastos Fijos",
                                 "Renta de máquina", 30)
        self.service.add_expense("2026-10-01", "Gastos variables",
                                 "Material de empaque", "20.50")
        summary = self.service.get_summary("2026-10-01")
        self.assertEqual(summary["gastos_centavos"], 5050)
        self.assertEqual(summary["saldo_esperado_centavos"], 19950)
        closing = self.service.confirm_closing(
            "2026-10-01", {("Billete", 100.0): 1,
                           ("Billete", 50.0): 1,
                           ("Billete", 20.0): 2}, 9.50
        )
        self.assertEqual(closing["saldo_contado_centavos"], 19950)
        next_day = self.service.get_summary("2026-10-02")
        self.assertEqual(next_day["saldo_inicial_centavos"], 19950)
        self.add_sale("2026-10-02", 50, 50)
        self.service.add_expense("2026-10-02", "Gastos variables",
                                 "Clips", 4.50)
        self.assertEqual(
            self.service.get_summary("2026-10-02")["saldo_esperado_centavos"],
            24500
        )

    def test_initial_fund_is_one_time_and_carries_forward(self):
        self.assertEqual(
            self.service.register_initial_fund("2026-10-01", "300.00"), 30000
        )
        self.assertEqual(
            self.service.get_summary("2026-10-01")["saldo_inicial_centavos"],
            30000,
        )
        with self.assertRaises(ValueError):
            self.service.register_initial_fund("2026-10-01", 50)
        self.service.add_expense(
            "2026-10-01", "Gastos variables", "Papel", 25
        )
        self.service.confirm_closing(
            "2026-10-01", {("Billete", 200.0): 1,
                           ("Billete", 50.0): 1,
                           ("Billete", 20.0): 1}, 5
        )
        next_day = self.service.get_summary("2026-10-02")
        self.assertEqual(next_day["saldo_inicial_centavos"], 27500)

    def test_initial_fund_cannot_be_added_after_first_closing(self):
        self.service.confirm_closing("2026-10-01", {}, 0)
        with self.assertRaises(ValueError):
            self.service.register_initial_fund("2026-10-02", 100)

    def test_unbalanced_closing_cannot_be_confirmed(self):
        self.add_sale("2026-10-01", 100, 100)
        with self.assertRaisesRegex(ValueError, "no cuadra"):
            self.service.confirm_closing("2026-10-01", {}, 80)
        self.assertIsNone(self.service.get_closing("2026-10-01"))

    def test_no_duplicate_closure_or_expense_edits_after_confirmation(self):
        self.add_sale("2026-10-01", 100, 100)
        self.service.confirm_closing("2026-10-01",
                                     {("Billete", 100.0): 1}, 0)
        with self.assertRaises(ValueError):
            self.service.confirm_closing("2026-10-01",
                                         {("Billete", 100.0): 1}, 0)
        with self.assertRaises(ValueError):
            self.service.add_expense("2026-10-01", "Gastos Fijos", "Luz", 5)
        with self.assertRaises(ValueError):
            self.service.delete_expense("2026-10-01", 9999)

    def test_no_expense_exceeding_cash_or_invalid_types(self):
        self.add_sale("2026-10-01", 100, 100)
        for kind, description, amount in [
            ("Otro", "Gasto", 5),
            ("Gastos Fijos", "", 5),
            ("Gastos Fijos", "Gasto", 101),
            ("Gastos Fijos", "Gasto", -1),
            ("Gastos Fijos", "Gasto", 1.234),
        ]:
            with self.subTest(kind=kind, description=description, amount=amount):
                with self.assertRaises(ValueError):
                    self.service.add_expense("2026-10-01", kind, description, amount)
        self.assertEqual(self.service.get_expenses("2026-10-01"), [])

    def test_delete_expense_prior_to_closing_restores_cash(self):
        self.add_sale("2026-10-01", 100, 100)
        expense_id = self.service.add_expense(
            "2026-10-01", "Gastos Fijos", "Limpieza", 20
        )
        self.assertEqual(
            self.service.get_summary("2026-10-01")["saldo_esperado_centavos"], 8000
        )
        self.service.delete_expense("2026-10-01", expense_id)
        self.assertEqual(
            self.service.get_summary("2026-10-01")["saldo_esperado_centavos"], 10000
        )

    def test_closed_later_day_prevents_retroactive_changes(self):
        self.add_sale("2026-10-02", 100, 100)
        self.service.confirm_closing("2026-10-02",
                                     {("Billete", 100.0): 1}, 0)
        with self.assertRaises(ValueError):
            self.service.add_expense("2026-10-01", "Gastos Fijos", "Luz", 1)
        with self.assertRaises(ValueError):
            self.service.confirm_closing("2026-10-01", {}, 0)

    def test_voided_expense_retains_audit_history(self):
        self.add_sale("2026-10-01", 100, 100)
        expense_id = self.service.add_expense(
            "2026-10-01", "Gastos variables", "Caja", 25
        )
        self.service.delete_expense("2026-10-01", expense_id)
        self.assertEqual(self.service.get_expenses("2026-10-01"), [])
        audit = self.db.cursor().execute(
            "SELECT anulado, anulado_en FROM gastos_caja WHERE id = ?",
            (expense_id,),
        ).fetchone()
        self.assertEqual(audit["anulado"], 1)
        self.assertIsNotNone(audit["anulado_en"])

    def test_historical_cash_count_is_restored_for_reports(self):
        self.add_sale("2026-10-01", 250, 250)
        self.service.confirm_closing(
            "2026-10-01", {("Billete", 200.0): 1}, 50
        )
        reconciliation = CashClosingService(self.db).calculate_cash_reconciliation(
            "2026-10-01", {}, 0
        )
        self.assertEqual(reconciliation["efectivo_contado"], 250)
        self.assertEqual(reconciliation["efectivo_esperado"], 250)
        self.assertEqual(reconciliation["morralla"], 50)
        denominations = {
            row["denominacion"]: row["cantidad"]
            for row in reconciliation["denominaciones"]
        }
        self.assertEqual(denominations[200], 1)
        self.assertEqual(reconciliation["estado"], "CUADRA")

    def test_sales_are_blocked_after_confirmed_today_close(self):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        self.service.confirm_closing(today, {}, 0)
        self.db.cursor().execute(
            """INSERT INTO productos (codigo, nombre, precio, existencia)
               VALUES ('CASH-LOCK', 'Caja cerrada', 10, 2)"""
        )
        self.db.commit()
        with self.assertRaisesRegex(ValueError, "ya está confirmado"):
            SaleService(self.db).create_sale(
                [{"producto_id": 1, "cantidad": 1, "precio_unitario": 10}],
                payment_method="Efectivo",
            )
        self.assertEqual(
            self.db.cursor().execute("SELECT COUNT(*) FROM ventas").fetchone()[0], 0
        )

    def test_cancellation_does_not_change_confirmed_cash(self):
        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO ventas
               (folio, fecha, hora, total, metodo_pago, total_neto)
               VALUES ('EARLY', '2026-10-01', '10:00:00', 50, 'Efectivo', 50)"""
        )
        cursor.execute(
            """INSERT INTO pagos_venta (venta_id, metodo_pago, monto)
               VALUES (?, 'Efectivo', 50)""", (cursor.lastrowid,)
        )
        self.db.commit()
        self.service.confirm_closing(
            "2026-10-01", {("Billete", 50.0): 1}, 0
        )
        with self.assertRaisesRegex(ValueError, "corte de caja confirmado"):
            SaleHistoryService(self.db).cancel_sale(1)

    def test_cannot_skip_unclosed_day_with_cash_sales(self):
        self.add_sale("2026-10-01", 100, 100)
        self.service.confirm_closing(
            "2026-10-01", {("Billete", 100.0): 1}, 0
        )
        self.add_sale("2026-10-02", 20, 20)
        with self.assertRaisesRegex(ValueError, "2026-10-02"):
            self.service.confirm_closing(
                "2026-10-03", {("Billete", 100.0): 1}, 0
            )
        self.service.confirm_closing(
            "2026-10-02", {("Billete", 100.0): 1,
                           ("Billete", 20.0): 1}, 0
        )
        self.assertEqual(
            self.service.get_summary("2026-10-03")["saldo_inicial_centavos"],
            12000
        )

    def test_sobre_valores_is_valid_and_deducted_from_cash(self):
        self.add_sale("2026-10-01", 100, 100)
        expense_id = self.service.add_expense(
            "2026-10-01", "Sobre/Valores", "Sobre de depósito", 30.50
        )
        summary = self.service.get_summary("2026-10-01")
        self.assertEqual(summary["gastos_centavos"], 3050)
        self.assertEqual(summary["saldo_esperado_centavos"], 6950)
        self.assertEqual(summary["gastos"][0]["tipo"], "Sobre/Valores")
        self.service.delete_expense("2026-10-01", expense_id)
        self.assertEqual(
            self.service.get_summary("2026-10-01")["gastos_centavos"], 0
        )

    def test_schema_migrates_existing_expenses_without_losing_history(self):
        cursor = self.db.cursor()
        cursor.execute("DROP TABLE gastos_caja")
        cursor.execute("""
            CREATE TABLE gastos_caja (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK (
                    tipo IN ('Gastos Fijos', 'Gastos variables')
                ),
                descripcion TEXT NOT NULL CHECK (LENGTH(TRIM(descripcion)) > 0),
                monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
                creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                anulado INTEGER NOT NULL DEFAULT 0 CHECK(anulado IN (0, 1)),
                anulado_en TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO gastos_caja
                (id, fecha, tipo, descripcion, monto_centavos, anulado)
            VALUES (15, '2026-10-01', 'Gastos variables', 'Papelería', 500, 1)
        """)
        self.db.commit()
        create_database(self.db)
        saved = self.db.cursor().execute(
            "SELECT id, tipo, descripcion, monto_centavos, anulado "
            "FROM gastos_caja WHERE id = 15"
        ).fetchone()
        self.assertEqual(tuple(saved), (15, "Gastos variables", "Papelería", 500, 1))
        expense_id = self.service.add_expense(
            "2026-10-01", "Sobre/Valores", "Sobre resguardado", 2
        )
        self.assertGreater(expense_id, 15)
        create_database(self.db)
        self.assertEqual(
            self.db.cursor().execute("PRAGMA integrity_check").fetchone()[0],
            "ok"
        )

    def test_schema_migration_is_idempotent(self):
        create_database(self.db)
        self.add_sale("2026-10-01", 100, 100)
        self.service.confirm_closing("2026-10-01",
                                     {("Billete", 100.0): 1}, 0)
        create_database(self.db)
        self.assertEqual(
            self.service.get_closing("2026-10-01")["saldo_contado_centavos"],
            10000,
        )
        self.assertEqual(self.db.cursor().execute(
            "PRAGMA integrity_check"
        ).fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
