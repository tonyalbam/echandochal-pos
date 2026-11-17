"""Evita altas duplicadas por nombre, categoría, marca, color y unidad."""

import os
import sqlite3
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog

from app.database.schema import create_database
from app.services.product_service import ProductService
from app.ui.product_dialog import ProductDialog


class MemoryDB:
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


class ProductDuplicatePreventionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDB()
        create_database(self.db)
        self.service = ProductService(self.db)
        self.category = next(
            row["id"] for row in self.service.get_categories()
            if row["nombre"] == "Algodón"
        )
        self.other_category = next(
            row["id"] for row in self.service.get_categories()
            if row["nombre"] == "Acrílico"
        )
        self.original_data = {
            "nombre": "Lana Arcoíris",
            "categoria_id": self.category,
            "marca": "Tejidos Sol",
            "color": "Rojo intenso",
            "unidad": "pieza",
            "costo": 30,
            "precio": 65,
            "existencia": 8,
            "stock_minimo": 2,
        }
        self.original_id = self.service.create_product(self.original_data)
        self.original_code = self.service.get_product(self.original_id)["codigo"]

    def tearDown(self):
        self.db.close()
        self.app.processEvents()

    def _count(self):
        return self.db.cursor().execute(
            "SELECT COUNT(*) FROM productos"
        ).fetchone()[0]

    def test_rejects_all_five_matching_even_with_different_prices_and_stock(self):
        data = {
            **self.original_data,
            "precio": 99,
            "costo": 50,
            "existencia": 500,
            "stock_minimo": 30,
        }
        duplicate = self.service.find_duplicate_product(data)
        self.assertEqual(duplicate["id"], self.original_id)
        with self.assertRaisesRegex(ValueError, "producto duplicado") as error:
            self.service.create_product(data)
        self.assertIn(self.original_code, str(error.exception))
        self.assertEqual(self._count(), 1)
        self.assertEqual(self.service.get_next_internal_code(), "ECH0000002")

    def test_ignores_case_and_extra_spaces_and_empty_brand_color(self):
        same = {
            **self.original_data,
            "nombre": "  lana  ARCOÍRIS  ",
            "marca": " tejidos   SOL ",
            "color": "rojo INTENSO ",
            "unidad": "PIEZA",
        }
        with self.assertRaises(ValueError):
            self.service.create_product(same)
        blank = {**self.original_data, "nombre": "Estambre Liso", "marca": "", "color": ""}
        self.service.create_product(blank)
        with self.assertRaises(ValueError):
            self.service.create_product({
                **blank, "marca": None, "color": "  ", "nombre": " estambre liso "
            })
        self.assertEqual(self._count(), 2)

    def test_allows_distinct_variants_of_each_identity_attribute(self):
        cases = [
            {"nombre": "Lana Arcoíris Fina"},
            {"categoria_id": self.other_category},
            {"marca": "Tejidos Luna"},
            {"color": "Azul"},
            {"unidad": "metro"},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                data = {**self.original_data, **changes}
                self.assertIsNone(self.service.find_duplicate_product(data))
                new_id = self.service.create_product(data)
                self.assertNotEqual(new_id, self.original_id)
        self.assertEqual(self._count(), 6)

    def test_inactive_product_still_blocks_duplicate(self):
        self.service.deactivate_product(self.original_id)
        result = self.service.find_duplicate_product(self.original_data)
        self.assertEqual(result["id"], self.original_id)
        self.assertEqual(result["activo"], 0)
        with self.assertRaisesRegex(ValueError, "desactivado"):
            self.service.create_product(self.original_data)
        self.assertEqual(self._count(), 1)

    def test_logically_deleted_product_does_not_block_new_product(self):
        self.service.delete_product(self.original_id)
        self.assertIsNone(self.service.find_duplicate_product(self.original_data))
        new_id = self.service.create_product(self.original_data)
        self.assertNotEqual(new_id, self.original_id)
        self.assertEqual(self._count(), 2)

    def test_new_product_dialog_warns_without_registering_duplicate(self):
        dialog = ProductDialog(self.service)
        dialog.show()
        self.app.processEvents()
        try:
            dialog.nombre.setText("lana arcoíris")
            dialog.nombre.editingFinished.emit()
            dialog.color.setText("  ROJO intenso ")
            self.assertEqual(dialog.categoria.currentData(), self.category)
            self.assertEqual(dialog.marca.text(), "Tejidos Sol")
            self.assertEqual(dialog.unidad.currentText(), "pieza")
            with patch.object(QMessageBox, "warning") as warning:
                dialog._save()
                warning.assert_called_once()
                args = warning.call_args.args
                self.assertEqual(args[1], "Producto duplicado")
                self.assertIn(self.original_code, args[2])
            self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
            self.assertEqual(self._count(), 1)
        finally:
            dialog.close()

    def test_new_product_dialog_can_save_different_color(self):
        dialog = ProductDialog(self.service)
        dialog.show()
        self.app.processEvents()
        try:
            dialog.nombre.setText("Lana Arcoíris")
            dialog.nombre.editingFinished.emit()
            dialog.color.setText("Azul celeste")
            with patch.object(QMessageBox, "warning") as warning:
                dialog._save()
                warning.assert_not_called()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
            self.assertEqual(self._count(), 2)
            added = max(self.service.list_products(), key=lambda x: x["id"])
            self.assertEqual(added["color"], "Azul celeste")
            self.assertEqual(added["marca"], "Tejidos Sol")
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
