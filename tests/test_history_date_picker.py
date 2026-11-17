"""Selección manual y calendario accesible para ambos historiales."""
import os
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QDateEdit, QCalendarWidget

from app.database.schema import create_database
from app.ui.sale_history_window import SaleHistoryWindow
from app.ui.purchase_history_window import PurchaseHistoryWindow


class MemoryDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()


class HistoryDateFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO proveedores(nombre) VALUES ('Proveedor fechas')")
        supplier_id = cursor.lastrowid
        cursor.executemany(
            """INSERT INTO ventas(
                folio, fecha, hora, subtotal, total,
                metodo_pago, monto_comision, total_neto)
               VALUES (?, ?, '12:00:00', 100, 100, 'Efectivo', 0, 100)""",
            (
                ("V-ANTIGUA", "2025-04-10"),
                ("V-RECIENTE", "2026-11-05"),
            ),
        )
        cursor.executemany(
            """INSERT INTO compras(
                folio, proveedor_id, fecha, subtotal, total)
               VALUES (?, ?, ?, 100, 100)""",
            (
                ("C-ANTIGUA", supplier_id, "2025-04-10"),
                ("C-RECIENTE", supplier_id, "2026-11-05"),
            ),
        )
        self.db.commit()
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.close()
        self.db.connection.close()

    def _window(self, klass):
        window = klass(self.db)
        self.windows.append(window)
        window.show()
        self.app.processEvents()
        return window

    def _verify_fields(self, window, from_edit, to_edit, from_button, to_button):
        for field, button in ((from_edit, from_button), (to_edit, to_button)):
            with self.subTest(field=field.objectName()):
                self.assertIsInstance(field, QDateEdit)
                self.assertTrue(field.isEnabled())
                self.assertFalse(field.isReadOnly())
                self.assertTrue(field.calendarPopup())
                self.assertEqual(field.displayFormat(), "yyyy-MM-dd")
                self.assertTrue(button.isEnabled())
                self.assertTrue(button.isVisible())
                self.assertIsInstance(button.calendar_widget, QCalendarWidget)

    def _pick_calendar(self, button, day):
        button.click()
        self.app.processEvents()
        self.assertTrue(button.calendar_popup.isVisible())
        self.assertEqual(
            button.calendar_widget.selectedDate(),
            button._linked_date_field.date(),
        )
        button.calendar_widget.clicked.emit(day)
        self.app.processEvents()
        self.assertFalse(button.calendar_popup.isVisible())

    def test_sale_history_dates_always_editable_and_calendar_filters(self):
        window = self._window(SaleHistoryWindow)
        start, end = window.fecha_desde, window.fecha_hasta
        self._verify_fields(
            window, start, end, window.calendario_desde, window.calendario_hasta,
        )
        self.assertFalse(window.filtrar_fechas.isChecked())
        self.assertEqual(len(window.sales), 2)

        end.setDate(QDate(2025, 12, 31))
        self.app.processEvents()
        self.assertTrue(window.filtrar_fechas.isChecked())
        self.assertEqual({item["folio"] for item in window.sales}, set())
        window.calendario_desde._linked_date_field = start
        self._pick_calendar(window.calendario_desde, QDate(2025, 1, 1))
        self.assertEqual(start.date(), QDate(2025, 1, 1))
        self.assertEqual(
            {item["folio"] for item in window.sales}, {"V-ANTIGUA"},
        )
        # Si se quita el filtro, los calendarios siguen disponibles.
        window.filtrar_fechas.setChecked(False)
        self.assertTrue(start.isEnabled())
        self.assertTrue(end.isEnabled())
        self.assertEqual(len(window.sales), 2)
        window.calendario_hasta._linked_date_field = end
        self._pick_calendar(window.calendario_hasta, QDate(2026, 11, 5))
        self.assertTrue(window.filtrar_fechas.isChecked())
        self.assertEqual(len(window.sales), 2)

    def test_purchase_history_dates_always_editable_and_calendar_filters(self):
        window = self._window(PurchaseHistoryWindow)
        start, end = window.date_from, window.date_to
        self._verify_fields(
            window, start, end, window.calendar_from, window.calendar_to,
        )
        self.assertFalse(window.filter_dates.isChecked())
        self.assertEqual(len(window.purchases), 2)
        end.setDate(QDate(2025, 12, 31))
        self.app.processEvents()
        self.assertTrue(window.filter_dates.isChecked())
        self.assertEqual(len(window.purchases), 0)

        window.calendar_from._linked_date_field = start
        self._pick_calendar(window.calendar_from, QDate(2025, 1, 1))
        self.assertEqual(
            {item["folio"] for item in window.purchases}, {"C-ANTIGUA"},
        )
        window.filter_dates.setChecked(False)
        self.assertTrue(start.isEnabled())
        self.assertTrue(end.isEnabled())
        self.assertEqual(len(window.purchases), 2)
        window.calendar_to._linked_date_field = end
        self._pick_calendar(window.calendar_to, QDate(2026, 11, 5))
        self.assertTrue(window.filter_dates.isChecked())
        self.assertEqual(len(window.purchases), 2)


if __name__ == "__main__":
    unittest.main()
