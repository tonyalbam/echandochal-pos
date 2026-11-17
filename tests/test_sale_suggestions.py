"""Regresión de sugerencias ampliadas en Nueva Venta."""

import os
import sqlite3
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app.database.schema import create_database
from app.services.product_service import ProductService
from app.services.sale_service import SaleService
from app.ui.sale_window import SaleWindow


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


class SaleSuggestionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        service = ProductService(self.db)
        category = next(
            c["id"] for c in service.get_categories()
            if c["nombre"] == "Algodón"
        )
        service.create_product({
            "nombre": "Estambre nube",
            "categoria_id": category,
            "marca": "Hilando",
            "color": "Azul marino",
            "unidad": "pieza",
            "costo": 10,
            "precio": 30,
            "existencia": 5,
        })
        service.create_product({
            "nombre": "Estambre nube",
            "categoria_id": category,
            "marca": "Hilando",
            "color": "Verde",
            "unidad": "pieza",
            "costo": 11,
            "precio": 35,
            "existencia": 4,
        })
        self.window = SaleWindow(self.db)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.db.close()
        self.app.processEvents()

    def test_search_returns_unit_in_addition_to_other_fields(self):
        results = SaleService(self.db).search_products("Estambre nube")
        self.assertEqual(len(results), 2)
        self.assertEqual({x["unidad"] for x in results}, {"pieza"})
        self.assertEqual({x["color"] for x in results}, {"Verde", "Azul marino"})
        self.assertEqual({x["categoria"] for x in results}, {"Algodón"})

    def test_suggestion_displays_code_name_brand_category_color_unit(self):
        self.window._actualizar_sugerencias("Estambre")
        labels = self.window.suggestion_model.stringList()
        self.assertEqual(len(labels), 2)
        for label in labels:
            parts = label.split(" | ")
            self.assertEqual(len(parts), 6)
            self.assertTrue(parts[0].startswith("ECH"))
            self.assertEqual(parts[1], "Estambre nube")
            self.assertEqual(parts[2], "Hilando")
            self.assertEqual(parts[3], "Algodón")
            self.assertIn(parts[4], ("Azul marino", "Verde"))
            self.assertEqual(parts[5], "pieza")
        self.assertNotEqual(labels[0], labels[1])
        self.assertGreaterEqual(
            self.window.completer.popup().minimumWidth(),
            self.window.codigo_input.width(),
        )
        self.assertEqual(
            self.window.completer.popup().textElideMode(),
            Qt.TextElideMode.ElideNone,
        )

    def test_selecting_suggestion_adds_exact_selected_product(self):
        self.window._actualizar_sugerencias("Estambre")
        labels = self.window.suggestion_model.stringList()
        green = next(label for label in labels if " | Verde | " in label)
        product = self.window.suggestion_products[green]
        self.window._agregar_sugerencia(green)
        self.assertEqual(len(self.window.items), 1)
        self.assertEqual(self.window.items[0]["producto_id"], product["id"])
        self.assertEqual(self.window.items[0]["color"], "Verde")
        self.assertEqual(self.window.items[0]["precio_unitario"], 35.0)

    def test_scanned_code_still_works(self):
        code = self.db.connection.execute(
            "SELECT codigo FROM productos WHERE color='Azul marino'"
        ).fetchone()[0]
        self.window.codigo_input.setText(code)
        with patch.object(QMessageBox, "warning") as warning:
            self.window._agregar_por_codigo()
            warning.assert_not_called()
        self.assertEqual(len(self.window.items), 1)
        self.assertEqual(self.window.items[0]["color"], "Azul marino")

    def test_missing_optional_values_use_clear_placeholders(self):
        self.db.cursor().execute(
            """INSERT INTO productos
               (codigo, nombre, precio, existencia, unidad, marca, color)
               VALUES ('S-NO-1', 'Producto sin datos', 12, 2, '', NULL, NULL)"""
        )
        self.db.commit()
        self.window._actualizar_sugerencias("Producto sin datos")
        labels = self.window.suggestion_model.stringList()
        self.assertEqual(len(labels), 1)
        self.assertIn("Sin marca", labels[0])
        self.assertIn("Sin categoría", labels[0])
        self.assertIn("Sin color", labels[0])
        self.assertIn("Sin unidad", labels[0])


if __name__ == "__main__":
    unittest.main()
