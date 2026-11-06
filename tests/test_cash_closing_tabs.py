"""Pestañas y ficha de utilidad emergente en el corte diario."""
import os
import sqlite3
import unittest
from datetime import date
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QTableWidget, QGroupBox
from PySide6.QtCore import QEvent

from app.database.schema import create_database
from app.services.petty_cash_service import PettyCashService
from app.ui.cash_closing_window import CashClosingWindow


class MemoryDatabase:
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


class GeneralTabsUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        self.window = CashClosingWindow(self.db)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.db.conn.close()

    def test_all_four_tabs_are_ordered_and_first_is_active_on_entry(self):
        self.assertEqual(self.window.tabs.count(), 4)
        self.assertEqual(
            [self.window.tabs.tabText(i) for i in range(4)], [
                "Corte general entradas/salidas",
                "Arqueo manual de efectivo",
                "Caja chica",
                "Corte general",
            ]
        )
        self.assertEqual(self.window.tabs.currentIndex(), 0)
        self.window.tabs.setCurrentIndex(2)
        self.window.on_enter()
        self.assertEqual(self.window.tabs.currentIndex(), 0)
        self.assertIsNotNone(
            self.window.general_flows_tab.findChild(
                QTableWidget, "accumulated_concepts"
            )
        )
        self.assertEqual(self.window.concepts_table.rowCount(), 9)

    def test_summary_hover_contains_complete_cost_table_instead_of_inline_section(self):
        self.assertEqual(len(self.window._profit_hover_targets), 2)
        self.assertIsNotNone(self.window._profit_popup)
        self.window._populate_profit_hover()
        self.assertEqual(
            self.window.profit_cost_table.horizontalHeaderItem(4).text(),
            "Costo de mercancía vendida",
        )
        self.assertIn("costo", self.window.profit_values)
        self.assertIn("gastos_operativos", self.window.profit_values)
        self.assertIn("utilidad_operativa", self.window.profit_values)
        self.assertEqual(
            self.window.values["utilidad"].text(),
            "$ 0.00",
        )
        self.assertNotIn(
            "Cómo se calcula la utilidad del día",
            [group.title() for group in self.window.findChildren(
                QGroupBox
            )],
        )

    def test_hover_over_title_or_amount_opens_profit_popup(self):
        for target in self.window._profit_hover_targets:
            self.window._profit_popup.hide()
            self.window.eventFilter(target, QEvent(QEvent.Type.Enter))
            self.app.processEvents()
            self.assertTrue(self.window._profit_popup.isVisible())
            self.assertEqual(
                self.window.profit_cost_table.horizontalHeaderItem(4).text(),
                "Costo de mercancía vendida",
            )
        self.window._profit_popup.hide()

    def test_concepts_show_accurate_daily_and_accumulated_values(self):
        self.assertEqual(self.window.concepts_table.item(0, 0).text(),
                         "Ventas netas en efectivo")
        self.assertEqual(self.window.concepts_table.item(0, 2).text(),
                         "$ 0.00")
        self.assertIn("Acumulado", self.window.accumulated_summary.text())

    def test_confirming_cash_refreshes_general_cut_without_manual_update(self):
        """Regresión: Caja chica CONFIRMADO y Corte general bloqueado."""
        today = date.today().isoformat()
        service = PettyCashService(self.db)
        service.register_initial_fund(today, 100)
        self.window.refresh()
        self.window.tabs.setCurrentIndex(3)
        self.assertFalse(self.window.confirm_general_button.isEnabled())
        self.window.tabs.setCurrentIndex(2)
        self.window.cash_inputs[("Billete", 100.0)].setText("1")
        self.assertEqual(self.window.cash_status.text(), "CUADRA")
        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.Yes), \
             patch.object(QMessageBox, "information"):
            self.window._confirm_closing()
        self.assertEqual(self.window.cash_status.text(), "CONFIRMADO")
        self.assertTrue(self.window.confirm_general_button.isEnabled())
        self.assertIn("pendiente", self.window.general_cut_status.text().lower())
        self.assertNotIn(
            "Primero confirma el corte de efectivo",
            self.window.general_cut_status.text()
        )
        self.window.tabs.setCurrentIndex(3)
        self.assertTrue(self.window.confirm_general_button.isEnabled())

    def test_tab_switch_detects_cash_close_from_other_screen(self):
        """El tab se actualiza aun cuando el cierre cambió fuera de la vista."""
        today = date.today().isoformat()
        self.window.tabs.setCurrentIndex(3)
        self.assertFalse(self.window.confirm_general_button.isEnabled())
        service = PettyCashService(self.db)
        service.confirm_closing(today, {}, 0)
        self.window.tabs.setCurrentIndex(2)
        self.window.tabs.setCurrentIndex(3)
        self.assertTrue(self.window.confirm_general_button.isEnabled())

    def test_register_general_cut_through_ui_after_cash_count(self):
        today = date.today().isoformat()
        PettyCashService(self.db).register_initial_fund(today, 100)
        PettyCashService(self.db).confirm_closing(
            today, {("Billete", 100.0): 1}, 0
        )
        self.window.refresh()
        self.window.tabs.setCurrentIndex(3)
        self.window.general_openings["Tarjeta"].setText("50")
        self.window.general_openings["Transferencia"].setText("75")
        self.window.general_actual["Efectivo"].setText("100")
        self.window.general_actual["Tarjeta"].setText("50")
        self.window.general_actual["Transferencia"].setText("75")
        self.assertTrue(self.window.confirm_general_button.isEnabled())
        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.Yes), \
             patch.object(QMessageBox, "information"):
            self.window._confirm_general_closing()
        self.assertIsNotNone(
            self.window.general_service.get_closing(today)
        )
        self.assertFalse(self.window.confirm_general_button.isEnabled())
        self.assertIn("CONFIRMADO", self.window.general_cut_status.text())
        self.assertEqual(
            self.window.general_real_labels["Efectivo"].text(), "$ 100.00"
        )


if __name__ == "__main__":
    unittest.main()
