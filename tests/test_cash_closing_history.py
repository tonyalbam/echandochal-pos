"""Historial mensual/anual de caja chica sin alterar saldos confirmados."""
import os
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from app.database.schema import create_database
from app.services.petty_cash_service import PettyCashService
from app.services.cash_closing_history_service import CashClosingHistoryService
from app.ui.cash_closing_history_window import CashClosingHistoryWindow, local_timestamp


class MemoryDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        return self.connection.commit()

    def rollback(self):
        return self.connection.rollback()


class CashClosingHistoryTest(unittest.TestCase):
    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        self.petty = PettyCashService(self.db)
        self.history = CashClosingHistoryService(self.db)
        self.petty.register_initial_fund("2026-08-01", 500)
        expense_id = self.petty.add_expense(
            "2026-08-02", "Gastos Fijos", "Luz", 100
        )
        self.petty.confirm_closing(
            "2026-08-02", {("Billete", 200.0): 2}, 0
        )
        self.petty.add_expense(
            "2026-09-01", "Sobre/Valores", "Sobre sellado", 50
        )
        self.petty.confirm_closing(
            "2026-09-01", {("Billete", 200.0): 1,
                           ("Billete", 100.0): 1,
                           ("Billete", 50.0): 1}, 0
        )
        self.petty.add_expense(
            "2026-10-04", "Gastos variables", "Cinta", 10
        )
        self.petty.add_expense(
            "2026-10-04", "Gastos Fijos", "Renta", 20
        )
        self.petty.delete_expense(
            "2026-10-04",
            self.petty.get_expenses("2026-10-04")[-1]["id"]
        )

    def tearDown(self):
        self.db.connection.close()

    def test_list_years_and_month_filters(self):
        self.assertEqual(self.history.list_years(), [2026])
        records = self.history.list_history(2026)
        self.assertEqual([r["fecha"] for r in records], [
            "2026-10-04", "2026-09-01", "2026-08-02"
        ])
        august = self.history.list_history(2026, 8)
        self.assertEqual(len(august), 1)
        self.assertEqual(august[0]["saldo_contado_centavos"], 40000)
        self.assertEqual(august[0]["gastos_centavos"], 10000)
        self.assertTrue(august[0]["confirmado"])
        self.assertEqual(self.history.list_history(2025), [])

    def test_daily_expenses_include_voided_but_do_not_sum_them(self):
        detail = self.history.get_day_detail("2026-10-04")
        self.assertIsNone(detail["cierre"])
        self.assertEqual(len(detail["gastos"]), 2)
        self.assertEqual([row["anulado"] for row in detail["gastos"]], [0, 1])
        self.assertEqual(detail["gastos_centavos"], 1000)
        self.assertEqual(detail["saldo_inicial_centavos"], 35000)
        self.assertEqual(detail["saldo_esperado_centavos"], 34000)

    def test_period_totals_sum_flows_not_balances(self):
        records = self.history.list_history(2026)
        summary = self.history.summarize(records)
        self.assertEqual(summary["dias"], 3)
        self.assertEqual(summary["confirmados"], 2)
        self.assertEqual(summary["gastos_centavos"], 16000)
        self.assertEqual(summary["saldo_inicial_centavos"], 50000)
        self.assertIsNone(summary["saldo_final_centavos"])
        september = self.history.summarize(
            self.history.list_history(2026, 9)
        )
        self.assertEqual(september["saldo_inicial_centavos"], 40000)
        self.assertEqual(september["saldo_final_centavos"], 35000)

    def test_does_not_mutate_daily_closing_or_expenses(self):
        before = self.db.connection.total_changes
        self.history.list_history(2026)
        self.history.get_day_detail("2026-09-01")
        self.assertEqual(self.db.connection.total_changes, before)


class CashClosingHistoryUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        petty = PettyCashService(self.db)
        petty.register_initial_fund("2026-09-01", 150)
        petty.add_expense("2026-09-01", "Sobre/Valores", "Sobre de caja", 50)
        petty.confirm_closing("2026-09-01", {
            ("Billete", 100.0): 1
        }, 0)
        self.window = CashClosingHistoryWindow(self.db)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.db.connection.close()

    def test_menu_filters_groups_and_day_detail(self):
        self.assertEqual(self.window.grouping.count(), 3)
        self.assertEqual(self.window.history.topLevelItemCount(), 1)
        year = self.window.history.topLevelItem(0)
        self.assertEqual(year.text(0), "2026")
        month = year.child(0)
        self.assertEqual(month.text(0), "Septiembre 2026")
        day = month.child(0)
        self.assertEqual(day.text(0), "2026-09-01")
        self.assertEqual(
            day.data(0, Qt.ItemDataRole.UserRole), "2026-09-01"
        )
        self.window.history.setCurrentItem(day)
        self.assertEqual(self.window.fields["saldo_contado_centavos"].text(), "$ 100.00")
        self.assertIn("CONFIRMADO", self.window.confirmation.text())
        self.assertEqual(self.window.expenses.rowCount(), 1)
        self.assertEqual(self.window.expenses.item(0, 0).text(), "Sobre/Valores")
        self.window.grouping.setCurrentText("Sin agrupar")
        self.assertEqual(self.window.history.topLevelItemCount(), 1)
        self.assertEqual(self.window.history.topLevelItem(0).text(0), "2026-09-01")
        self.window.grouping.setCurrentText("Año")
        self.assertEqual(self.window.history.topLevelItem(0).child(0).text(0),
                         "2026-09-01")

    def test_utc_registration_at_midnight_displays_previous_mexico_date(self):
        # SQLite CURRENT_TIMESTAMP es UTC. En México el evento ocurrió
        # el día 05, aunque el registro tenga fecha UTC del 06.
        self.assertEqual(
            local_timestamp("2026-11-06 03:23:27"),
            "2026-11-05 21:23:27",
        )
        self.assertEqual(
            local_timestamp("2026-11-05 18:45:00"),
            "2026-11-05 12:45:00",
        )

    def test_cancelled_expense_label_and_local_dates_do_not_change_db(self):
        cursor = self.db.cursor()
        cursor.execute(
            """UPDATE gastos_caja SET creado_en = ?,
                      anulado = 1, anulado_en = ?
               WHERE fecha = ?""",
            ("2026-11-06 03:23:27", "2026-11-06 03:24:00",
             "2026-09-01"),
        )
        cursor.execute(
            "UPDATE cierres_caja SET confirmado_en = ? WHERE fecha = ?",
            ("2026-11-06 03:23:27", "2026-09-01"),
        )
        self.db.commit()
        self.window.refresh()
        self.assertEqual(self.window.expenses.item(0, 3).text(), "CANCELADA")
        self.assertEqual(
            self.window.expenses.item(0, 4).text(),
            "2026-11-05 21:23:27",
        )
        self.assertIn("2026-11-05 21:23:27", self.window.confirmation.text())
        self.assertEqual(
            self.db.cursor().execute(
                "SELECT creado_en FROM gastos_caja WHERE fecha = ?",
                ("2026-09-01",),
            ).fetchone()[0],
            "2026-11-06 03:23:27",
        )

    def test_cash_balance_heading_has_requested_text(self):
        labels = [
            label.text() for label in self.window.findChildren(QLabel)
        ]
        self.assertIn(
            "Monto de efectivo que debe tener la caja chica", labels
        )
        self.assertEqual(
            self.window.fields["saldo_contado_centavos"].text(),
            "$ 100.00",
        )

    def test_year_and_month_filters(self):
        self.window.year.setCurrentIndex(self.window.year.findData(2026))
        self.window.month.setCurrentIndex(self.window.month.findData(9))
        self.assertEqual(self.window.history.topLevelItemCount(), 1)
        self.window.month.setCurrentIndex(self.window.month.findData(3))
        self.assertEqual(self.window.history.topLevelItemCount(), 0)
        self.assertEqual(self.window.expenses.rowCount(), 0)
        self.window.month.setCurrentIndex(self.window.month.findData(9))
        self.assertEqual(self.window.history.topLevelItemCount(), 1)


if __name__ == "__main__":
    unittest.main()
