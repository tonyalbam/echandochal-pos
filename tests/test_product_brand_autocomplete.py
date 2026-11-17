"""Sugerencias de marcas al registrar un producto nuevo."""

import os
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCompleter

from app.database.schema import create_database
from app.services.product_service import ProductService
from app.ui.product_dialog import ProductDialog


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

    def close(self):
        self.connection.close()


class ProductBrandAutocompleteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        self.service = ProductService(self.db)
        self.category = self.service.get_categories()[0]["id"]
        self.brand_ids = {}
        for i, (name, brand) in enumerate((
            ("Estambre 1", "Katia"),
            ("Estambre 2", "DMC"),
            ("Estambre 3", "Lana Katia"),
            ("Estambre 4", "katia"),
            ("Estambre 5", "  DMC  "),
            ("Estambre 6", "Lion Brand"),
            ("Estambre 7", " "),
        ), 1):
            self.brand_ids[name] = self.service.create_product({
                "nombre": name, "marca": brand,
                "categoria_id": self.category,
                "unidad": "pieza", "precio": 20,
            })

    def tearDown(self):
        self.db.close()
        self.app.processEvents()

    def _dialog(self):
        dialog = ProductDialog(self.service)
        dialog.show()
        self.app.processEvents()
        return dialog

    def test_brands_unique_sorted_case_insensitive_and_trimmed(self):
        self.assertEqual(
            self.service.get_registered_brands(),
            ["DMC", "Katia", "Lana Katia", "Lion Brand"],
        )

    def test_inactive_brands_remain_available_but_deleted_do_not(self):
        self.service.deactivate_product(self.brand_ids["Estambre 6"])
        self.service.delete_product(self.brand_ids["Estambre 3"])
        self.assertEqual(
            self.service.get_registered_brands(),
            ["DMC", "Katia", "Lion Brand"],
        )

    def test_new_product_brand_has_contains_autocomplete(self):
        dialog = self._dialog()
        try:
            completer = dialog.marca.completer()
            self.assertIs(completer, dialog.brand_completer)
            self.assertEqual(
                completer.caseSensitivity(),
                Qt.CaseSensitivity.CaseInsensitive,
            )
            self.assertEqual(completer.filterMode(), Qt.MatchFlag.MatchContains)
            self.assertEqual(
                completer.completionMode(),
                QCompleter.CompletionMode.PopupCompletion,
            )
            completer.setCompletionPrefix("at")
            self.assertEqual(completer.completionCount(), 2)
            matches = {
                completer.completionModel().index(i, 0).data()
                for i in range(completer.completionCount())
            }
            self.assertEqual(matches, {"Katia", "Lana Katia"})
            completer.setCompletionPrefix("liON")
            self.assertEqual(completer.completionCount(), 1)
            self.assertEqual(completer.currentCompletion(), "Lion Brand")
        finally:
            dialog.close()

    def test_typing_in_brand_displays_suggestion_popup(self):
        dialog = self._dialog()
        try:
            dialog.marca.setFocus()
            QTest.keyClicks(dialog.marca, "dM")
            self.app.processEvents()
            self.assertEqual(dialog.marca.text(), "dM")
            self.assertEqual(dialog.brand_completer.completionCount(), 1)
            self.assertEqual(
                dialog.brand_completer.currentCompletion(), "DMC"
            )
            self.assertTrue(dialog.brand_completer.popup().isVisible())
        finally:
            dialog.close()

    def test_keyboard_enter_chooses_matching_brand(self):
        dialog = self._dialog()
        try:
            dialog.marca.setFocus()
            QTest.keyClicks(dialog.marca, "lion")
            self.app.processEvents()
            self.assertTrue(dialog.brand_completer.popup().isVisible())
            QTest.keyClick(dialog.marca, Qt.Key.Key_Down)
            QTest.keyClick(dialog.marca, Qt.Key.Key_Return)
            self.app.processEvents()
            self.assertEqual(dialog.marca.text(), "Lion Brand")
        finally:
            dialog.close()

    def test_mouse_selects_matching_brand(self):
        dialog = self._dialog()
        try:
            dialog.marca.setFocus()
            QTest.keyClicks(dialog.marca, "atia")
            self.app.processEvents()
            completer = dialog.brand_completer
            self.assertTrue(completer.popup().isVisible())
            popup = completer.popup()
            idx = completer.completionModel().index(0, 0)
            QTest.mouseClick(
                popup.viewport(),
                Qt.MouseButton.LeftButton,
                pos=popup.visualRect(idx).center(),
            )
            self.app.processEvents()
            self.assertIn(dialog.marca.text(), {"Katia", "Lana Katia"})
        finally:
            dialog.close()

    def test_new_brand_can_be_typed_saved_and_suggested_later(self):
        dialog = self._dialog()
        try:
            dialog.nombre.setText("Nuevo artículo de prueba")
            dialog.marca.setText("Marca completamente nueva")
            dialog._save()
            self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)
        finally:
            dialog.close()

        self.assertIn("Marca completamente nueva", self.service.get_registered_brands())
        second = self._dialog()
        try:
            second.brand_completer.setCompletionPrefix("completamente")
            self.assertEqual(second.brand_completer.completionCount(), 1)
            self.assertEqual(
                second.brand_completer.currentCompletion(),
                "Marca completamente nueva",
            )
        finally:
            second.close()

    def test_name_prefill_still_sets_brand_without_changing_record(self):
        dialog = self._dialog()
        try:
            dialog.nombre.setText("Estambre 1")
            dialog.nombre.editingFinished.emit()
            self.assertEqual(dialog.marca.text(), "Katia")
            self.assertEqual(dialog.categoria.currentData(), self.category)
            self.assertTrue(dialog.marca.isEnabled())
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
