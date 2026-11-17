"""Nuevo producto: sugerencias por nombre y campos numéricos de captura limpia."""

import os
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit

from app.database.schema import create_database
from app.services.product_service import ProductService
from app.ui.product_dialog import ProductDialog, ProductNumericInput


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


class ProductNamePrefillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        self.service = ProductService(self.db)
        self.category = next(
            value["id"] for value in self.service.get_categories()
            if value["nombre"] == "Algodón"
        )
        self.supplier = self.service.create_supplier("Proveedor pruebas")
        self.source_id = self.service.create_product({
            "nombre": "Algodón París",
            "categoria_id": self.category,
            "marca": "Marca original",
            "color": "Rojo",
            "unidad": "pieza",
            "costo": 38.25,
            "precio": 79.50,
            "existencia": 25,
            "stock_minimo": 4,
            "proveedor_id": self.supplier,
            "codigo_barras": "ABC0123",
            "codigo_qr": "QR-ABC0123",
        })
        self.source = self.service.get_product(self.source_id)
        self.dialog = ProductDialog(self.service)
        self.dialog.show()
        self.app.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.db.close()
        self.app.processEvents()

    def _match(self, name=" algodón PARÍS "):
        self.dialog.nombre.setText(name)
        self.dialog.nombre.editingFinished.emit()
        self.app.processEvents()

    def test_finds_same_name_ignoring_case_and_spaces(self):
        found = self.service.find_existing_by_name("  algodón  PARÍS ")
        self.assertEqual(found["id"], self.source_id)
        self.assertIsNone(self.service.find_existing_by_name("Algodón diferente"))

    def test_prefills_only_requested_attributes_and_keeps_fields_editable(self):
        self._match()
        d = self.dialog
        self.assertEqual(d.categoria.currentData(), self.category)
        self.assertEqual(d.marca.text(), "Marca original")
        self.assertEqual(d.unidad.currentText(), "pieza")
        self.assertEqual(d.costo.value(), 38.25)
        self.assertEqual(d.precio.value(), 79.5)
        self.assertEqual(d.stock_minimo.value(), 4)
        self.assertEqual(d.proveedor.currentData(), self.supplier)

        # Identificadores, color e inventario NO se heredan del modelo.
        self.assertNotEqual(d.codigo.text(), self.source["codigo"])
        self.assertEqual(d.codigo_barras.text(), "")
        self.assertEqual(d.codigo_qr.text(), "")
        self.assertEqual(d.color.text(), "")
        self.assertEqual(d.existencia.value(), 0.0)
        self.assertIn(self.source["codigo"], d.prefill_hint.text())
        self.assertFalse(d.marca.isReadOnly())
        self.assertFalse(d.costo.isReadOnly())

    def test_manual_override_is_not_lost_when_focus_moves(self):
        self._match()
        d = self.dialog
        d.marca.setText("Otra marca")
        d.costo.setValue(41)
        d.precio.setValue(86)
        d.nombre.setFocus()
        self.app.processEvents()
        d.color.setFocus()
        self.app.processEvents()
        self.assertEqual(d.marca.text(), "Otra marca")
        self.assertEqual(d.costo.value(), 41)
        self.assertEqual(d.precio.value(), 86)

    def test_saved_similar_product_has_its_own_stock_and_codes(self):
        self._match()
        d = self.dialog
        d.marca.setText("Marca alternativa")
        d.costo.setValue(45)
        d.existencia.setValue(3)
        d._save()
        self.assertEqual(d.result(), d.DialogCode.Accepted)
        all_products = self.service.list_products()
        self.assertEqual(len(all_products), 2)
        new = next(x for x in all_products if x["id"] != self.source_id)
        self.assertEqual(new["marca"], "Marca alternativa")
        self.assertEqual(new["costo"], 45)
        self.assertEqual(new["precio"], 79.5)
        self.assertEqual(new["stock_minimo"], 4)
        self.assertEqual(new["existencia"], 3)
        self.assertNotEqual(new["codigo"], self.source["codigo"])
        self.assertEqual(new["codigo_barras"], None)
        self.assertEqual(new["codigo_qr"], None)
        self.assertEqual(new["color"], "")
        self.assertEqual(self.service.get_product(self.source_id)["existencia"], 25)

    def test_no_match_does_not_replace_form_values(self):
        self.dialog.marca.setText("Capturada por usuario")
        self.dialog.nombre.setText("No existe este nombre")
        self.dialog.nombre.editingFinished.emit()
        self.assertEqual(self.dialog.marca.text(), "Capturada por usuario")
        self.assertEqual(self.dialog.prefill_hint.text(), "")

    def test_numeric_fields_are_editable_text_not_spinboxes(self):
        for field in (
            self.dialog.costo, self.dialog.precio,
            self.dialog.existencia, self.dialog.stock_minimo,
        ):
            with self.subTest(field=field):
                self.assertIsInstance(field, ProductNumericInput)
                self.assertIsInstance(field, QLineEdit)
                self.assertNotIsInstance(field, QDoubleSpinBox)
                self.assertIsNotNone(field.validator())

    def test_focus_clears_previous_value_and_backspace_remains_blank(self):
        for field in (
            self.dialog.costo, self.dialog.precio,
            self.dialog.existencia, self.dialog.stock_minimo,
        ):
            with self.subTest(field=field):
                field.setValue(123.5)
                self.dialog.marca.setFocus()
                self.app.processEvents()
                field.setFocus()
                self.app.processEvents()
                self.assertEqual(field.text(), "")
                QTest.keyClicks(field, "42")
                self.assertEqual(field.value(), 42)
                field.selectAll()
                QTest.keyClick(field, Qt.Key.Key_Backspace)
                self.assertEqual(field.text(), "")
                self.dialog.marca.setFocus()
                self.app.processEvents()
                self.assertEqual(field.text(), "")
                self.assertEqual(field.value(), 0)

    def test_blanked_cost_stays_zero_on_save(self):
        self._match()
        self.dialog.costo.setFocus()
        self.app.processEvents()
        self.assertEqual(self.dialog.costo.text(), "")
        self.dialog.marca.setFocus()
        self.app.processEvents()
        self.assertEqual(self.dialog.costo.text(), "")
        self.dialog._save()
        new = max(self.service.list_products(), key=lambda x: x["id"])
        self.assertEqual(new["costo"], 0)
        self.assertEqual(new["precio"], 79.5)

    def test_rejects_letters_and_excess_decimal_places(self):
        d = self.dialog
        d.costo.setFocus()
        self.app.processEvents()
        QTest.keyClicks(d.costo, "12.345abc")
        self.assertEqual(d.costo.text(), "12.34")
        d.existencia.setFocus()
        self.app.processEvents()
        QTest.keyClicks(d.existencia, "3.4567abc")
        self.assertEqual(d.existencia.text(), "3.456")

    def test_edit_product_does_not_autofill_or_wipe_untouched_values(self):
        edited = ProductDialog(self.service, self.source)
        edited.show()
        self.app.processEvents()
        try:
            self.assertEqual(edited.costo.value(), 38.25)
            edited.costo.setFocus()
            self.app.processEvents()
            self.assertEqual(edited.costo.value(), 38.25)
            edited.marca.setFocus()
            self.app.processEvents()
            self.assertEqual(edited.costo.value(), 38.25)
            edited.nombre.setText("Algodón París")
            edited.nombre.editingFinished.emit()
            self.assertEqual(edited.prefill_hint.text(), "")
        finally:
            edited.close()


if __name__ == "__main__":
    unittest.main()
