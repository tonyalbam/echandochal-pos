"""Sugerencias de Nueva Compra con seis atributos y selección correcta."""

import os
import sqlite3
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app.database.schema import create_database
from app.services.product_service import ProductService
from app.services.purchase_service import PurchaseService
from app.ui.purchase_window import PurchaseWindow


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


class PurchaseSuggestionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        service = ProductService(self.db)
        category_id = next(
            x["id"] for x in service.get_categories()
            if x["nombre"] == "Algodón"
        )
        for color, cost in (("Azul marino", 15.5), ("Verde", 19)):
            service.create_product({
                "nombre": "Estambre nube",
                "categoria_id": category_id,
                "marca": "Hilando",
                "color": color,
                "unidad": "pieza",
                "costo": cost,
                "precio": 40,
                "existencia": 5,
            })
        self.window = PurchaseWindow(self.db)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.db.close()
        self.app.processEvents()

    def test_purchase_search_already_includes_category_color_and_unit(self):
        products = PurchaseService(self.db).search_products("Estambre nube")
        self.assertEqual(len(products), 2)
        self.assertEqual({p["categoria"] for p in products}, {"Algodón"})
        self.assertEqual({p["color"] for p in products}, {"Azul marino", "Verde"})
        self.assertEqual({p["unidad"] for p in products}, {"pieza"})

    def test_popup_displays_all_six_fields(self):
        self.window._update_suggestions("Estambre")
        labels = self.window.suggestion_model.stringList()
        self.assertEqual(len(labels), 2)
        for label in labels:
            code, name, brand, category, color, unit = label.split(" | ")
            self.assertTrue(code.startswith("ECH"))
            self.assertEqual(name, "Estambre nube")
            self.assertEqual(brand, "Hilando")
            self.assertEqual(category, "Algodón")
            self.assertIn(color, {"Azul marino", "Verde"})
            self.assertEqual(unit, "pieza")
        self.assertNotEqual(labels[0], labels[1])
        self.assertEqual(
            self.window.completer.popup().textElideMode(),
            Qt.TextElideMode.ElideNone,
        )
        self.assertGreaterEqual(
            self.window.completer.popup().minimumWidth(),
            self.window.product_search.width(),
        )

    def test_selection_adds_exact_color_and_cost_without_duplicates(self):
        self.window._update_suggestions("Estambre")
        label = next(
            item for item in self.window.suggestion_model.stringList()
            if " | Verde | " in item
        )
        chosen = self.window.suggestion_products[label]
        self.window._add_suggestion(label)
        self.assertEqual(len(self.window.items), 1)
        self.assertEqual(self.window.items[0]["producto_id"], chosen["id"])
        self.assertEqual(self.window.items[0]["color"], "Verde")
        self.assertEqual(self.window.items[0]["costo_unitario"], 19)
        # Enter sobre el menú no debe agregar el mismo producto dos veces.
        self.window._add_product()
        self.assertEqual(len(self.window.items), 1)

    def test_barcode_entry_still_adds_product(self):
        code = self.db.cursor().execute(
            "SELECT codigo FROM productos WHERE color = 'Azul marino'"
        ).fetchone()[0]
        self.window.product_search.setText(code)
        with patch.object(QMessageBox, "warning") as warning:
            self.window._add_product()
            warning.assert_not_called()
        self.assertEqual(len(self.window.items), 1)
        self.assertEqual(self.window.items[0]["color"], "Azul marino")

    def test_missing_fields_display_clear_placeholders(self):
        self.db.cursor().execute(
            """INSERT INTO productos
               (codigo, nombre, unidad, marca, color, costo)
               VALUES ('CMP-NULL', 'Sin atributos', '', NULL, NULL, 0)"""
        )
        self.db.commit()
        self.window._update_suggestions("Sin atributos")
        labels = self.window.suggestion_model.stringList()
        self.assertEqual(len(labels), 1)
        self.assertIn("Sin marca", labels[0])
        self.assertIn("Sin categoría", labels[0])
        self.assertIn("Sin color", labels[0])
        self.assertIn("Sin unidad", labels[0])


if __name__ == "__main__":
    unittest.main()
