"""Corte general con saldos bancarios explícitos y conceptos acumulados."""
import sqlite3
import unittest
from datetime import date, timedelta

from app.database.schema import create_database
from app.services.general_closing_service import GeneralClosingService
from app.services.petty_cash_service import PettyCashService


class MemoryDb:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")

    def cursor(self):
        return self.conn.cursor()

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


class GeneralClosingTest(unittest.TestCase):
    def setUp(self):
        self.db = MemoryDb()
        create_database(self.db)
        self.petty = PettyCashService(self.db)
        self.service = GeneralClosingService(self.db)
        self.day = date.today().isoformat()
        self.prior = (date.today() - timedelta(days=1)).isoformat()

    def tearDown(self):
        self.db.conn.close()

    def sale(self, day, cash=0, card=0, transfer=0):
        total = cash + card + transfer
        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO ventas(folio,fecha,hora,subtotal,total,
               metodo_pago,monto_comision,total_neto)
               VALUES(?,?,'09:00:00',? ,?, 'Mixto',?,?)""",
            (f"V-GEN-{day}-{self.db.conn.total_changes}",
             day, total, total, card * .04, total - card * .04),
        )
        sale_id = cursor.lastrowid
        for method, value, fee in (
            ("Efectivo", cash, 0),
            ("Mercado Libre", card, card * .04),
            ("Transferencia", transfer, 0),
        ):
            if value:
                cursor.execute(
                    "INSERT INTO pagos_venta(venta_id,metodo_pago,monto,monto_comision) "
                    "VALUES(?,?,?,?)",
                    (sale_id, method, value, fee),
                )
        self.db.commit()

    def purchase(self, day, cash=0, card=0, transfer=0):
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO proveedores(nombre) VALUES('P')")
        supplier = cursor.lastrowid
        total = cash + card + transfer
        cursor.execute(
            """INSERT INTO compras(folio,proveedor_id,fecha,subtotal,total)
               VALUES(?,?,?,?,?)""",
            (f"C-GEN-{day}-{self.db.conn.total_changes}",
             supplier, day, total, total),
        )
        purchase_id = cursor.lastrowid
        for method, value in (
            ("Efectivo", cash), ("Tarjeta", card),
            ("Transferencia", transfer),
        ):
            if value:
                cursor.execute(
                    "INSERT INTO pagos_compra(compra_id,metodo_pago,monto_centavos) "
                    "VALUES(?,?,?)",
                    (purchase_id, method, int(value * 100)),
                )
        self.db.commit()

    def setup_flows(self):
        self.petty.register_initial_fund(self.day, 500)
        self.sale(self.day, cash=50, card=100, transfer=200)
        self.purchase(self.day, cash=100, card=80, transfer=50)
        self.petty.add_expense(
            self.day, "Gastos Fijos", "Renta", 20
        )
        self.petty.confirm_closing(
            self.day, {("Billete", 200.0): 2, ("Billete", 20.0): 1}, 10
        )

    def test_first_general_close_requires_cash_close_and_opening_bank_balances(self):
        with self.assertRaisesRegex(ValueError, "Primero confirma"):
            self.service.confirm(
                self.day,
                {"Efectivo": 0, "Tarjeta": 0, "Transferencia": 0},
                {"Tarjeta": 100, "Transferencia": 200},
            )
        self.setup_flows()
        with self.assertRaisesRegex(ValueError, "saldos iniciales"):
            self.service.confirm(
                self.day,
                {"Efectivo": 430, "Tarjeta": 310, "Transferencia": 352},
                {},
            )

    def test_daily_flows_and_concepts_are_not_double_counted(self):
        self.setup_flows()
        summary = self.service.get_summary(
            self.day, initial_card=300, initial_transfer=200
        )
        rows = {r["metodo_pago"]: r for r in summary["medios"]}
        self.assertEqual(rows["Efectivo"]["saldo_esperado_centavos"], 43000)
        self.assertEqual(rows["Tarjeta"]["saldo_esperado_centavos"], 31600)
        self.assertEqual(rows["Transferencia"]["saldo_esperado_centavos"], 35000)
        concepts = {
            x["clave"]: x
            for x in self.service.get_concept_movements(self.day)
        }
        self.assertEqual(concepts["venta_efectivo"]["dia_centavos"], 5000)
        self.assertEqual(concepts["venta_tarjeta"]["dia_centavos"], 9600)
        self.assertEqual(concepts["venta_transferencia"]["dia_centavos"], 20000)
        self.assertEqual(concepts["compra_efectivo"]["dia_centavos"], 10000)
        self.assertEqual(concepts["compra_tarjeta"]["dia_centavos"], 8000)
        self.assertEqual(concepts["compra_transferencia"]["dia_centavos"], 5000)
        self.assertEqual(concepts["gasto_fijo"]["dia_centavos"], 2000)
        self.assertEqual(concepts["sobre_valores"]["dia_centavos"], 0)
        for item in concepts.values():
            self.assertEqual(item["dia_centavos"], item["acumulado_centavos"])

    def test_confirmation_preserves_differences_and_next_day_carryover(self):
        self.setup_flows()
        recorded = self.service.confirm(
            self.day,
            {"Efectivo": 430, "Tarjeta": 310, "Transferencia": 352},
            {"Tarjeta": 300, "Transferencia": 200},
            "Conciliado con extractos",
        )
        self.assertEqual(recorded["medios"]["Tarjeta"]["diferencia_centavos"], -600)
        self.assertEqual(recorded["medios"]["Transferencia"]["diferencia_centavos"], 200)
        self.assertEqual(recorded["medios"]["Efectivo"]["diferencia_centavos"], 0)
        with self.assertRaisesRegex(ValueError, "ya está confirmado"):
            self.service.confirm(
                self.day, {"Efectivo":430,"Tarjeta":310,"Transferencia":352}, {}
            )
        next_day = (date.today() + timedelta(days=1)).isoformat()
        next_summary = self.service.get_summary(next_day)
        mapping = {r["metodo_pago"]: r for r in next_summary["medios"]}
        self.assertEqual(mapping["Tarjeta"]["saldo_inicial_centavos"], 31000)
        self.assertEqual(mapping["Transferencia"]["saldo_inicial_centavos"], 35200)
        self.assertEqual(mapping["Efectivo"]["saldo_inicial_centavos"], 43000)
        create_database(self.db)
        self.assertEqual(self.service.get_closing(self.day)["notas"],
                         "Conciliado con extractos")

    def test_general_cash_cannot_disagree_with_confirmed_cash_count(self):
        self.setup_flows()
        with self.assertRaisesRegex(ValueError, "debe coincidir"):
            self.service.confirm(
                self.day,
                {"Efectivo": 420, "Tarjeta": 310, "Transferencia": 352},
                {"Tarjeta": 300, "Transferencia": 200},
            )
        self.assertIsNone(self.service.get_closing(self.day))

    def test_cancelled_expenses_not_in_accumulated_concepts(self):
        self.petty.register_initial_fund(self.day, 500)
        expense = self.petty.add_expense(
            self.day, "Gastos variables", "Borrado", 90
        )
        self.petty.delete_expense(self.day, expense)
        data = {row["clave"]: row
                for row in self.service.get_concept_movements(self.day)}
        self.assertEqual(data["gasto_variable"]["dia_centavos"], 0)
        self.assertEqual(data["gasto_variable"]["acumulado_centavos"], 0)

    def test_skipped_day_with_transactions_cannot_be_ignored(self):
        self.petty.register_initial_fund(self.prior, 100)
        self.petty.confirm_closing(
            self.prior, {("Billete", 100.0): 1}, 0
        )
        self.service.confirm(
            self.prior,
            {"Efectivo": 100, "Tarjeta": 100, "Transferencia": 100},
            {"Tarjeta": 100, "Transferencia": 100},
        )
        self.sale(self.day, cash=0, card=50)
        future = (date.today() + timedelta(days=1)).isoformat()
        # Crear un cierre ficticio de caja chica para la fecha futura no
        # aplica: la verificación de no saltar días ocurre en el servicio.
        with self.assertRaisesRegex(ValueError, "Primero confirma"):
            self.service.confirm(
                future,
                {"Efectivo": 100, "Tarjeta": 150, "Transferencia": 100},
                {},
            )

    def test_initial_bank_balances_can_be_zero_explicitly(self):
        self.petty.confirm_closing(self.day, {}, 0)
        self.service.confirm(
            self.day,
            {"Efectivo": 0, "Tarjeta": 0, "Transferencia": 0},
            {"Tarjeta": 0, "Transferencia": 0},
        )
        self.assertEqual(
            self.service.get_closing(self.day)["medios"]["Tarjeta"]["saldo_real_centavos"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
