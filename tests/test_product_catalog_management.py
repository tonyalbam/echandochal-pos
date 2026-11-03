"""Catálogos personalizables sin pérdida de datos existentes."""
import sqlite3
import unittest

from app.database.schema import create_database
from app.services.product_service import ProductService


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


class ProductCatalogManagementTest(unittest.TestCase):
    def setUp(self):
        self.db = MemoryDB()
        create_database(self.db)
        self.service = ProductService(self.db)

    def tearDown(self):
        self.db.connection.close()

    def test_add_category_and_unit_and_use_them_for_product(self):
        category_id = self.service.add_catalog_option("categorias", "Lanas especiales")
        self.service.add_catalog_option("unidades", "cono")
        product_id = self.service.create_product({
            "nombre": "Cono de lana", "categoria_id": category_id, "unidad": "cono"
        })
        self.assertEqual(self.service.get_product(product_id)["categoria_nombre"],
                         "Lanas especiales")
        self.assertEqual(self.service.get_product(product_id)["unidad"], "cono")
        self.assertIn("Lanas especiales",
                      [x["nombre"] for x in self.service.get_categories()])
        self.assertIn("cono", [x["nombre"] for x in self.service.get_units()])

    def test_removed_option_disappears_but_product_remains_and_can_be_restored(self):
        category_id = self.service.add_catalog_option("categorias", "Temporal")
        unit_id = self.service.add_catalog_option("unidades", "rollito")
        product_id = self.service.create_product({
            "nombre": "Referencia histórica", "categoria_id": category_id,
            "unidad": "rollito"
        })
        self.service.remove_catalog_option("categorias", category_id)
        self.service.remove_catalog_option("unidades", unit_id)
        self.assertNotIn("Temporal",
                         [x["nombre"] for x in self.service.get_categories()])
        self.assertNotIn("rollito", [x["nombre"] for x in self.service.get_units()])
        self.assertEqual(self.service.get_product(product_id)["categoria_nombre"],
                         "Temporal")
        self.assertEqual(self.service.get_product(product_id)["unidad"], "rollito")
        self.assertEqual(self.db.cursor().execute(
            "PRAGMA foreign_key_check"
        ).fetchall(), [])
        create_database(self.db)
        self.assertNotIn("Temporal",
                         [x["nombre"] for x in self.service.get_categories()])
        self.assertNotIn("rollito", [x["nombre"] for x in self.service.get_units()])
        self.assertEqual(self.service.add_catalog_option("categorias", "temporal"),
                         category_id)
        self.assertEqual(self.service.add_catalog_option("unidades", "ROLLITO"),
                         unit_id)

    def test_original_category_is_not_reactivated_on_startup(self):
        category_id = next(
            x["id"] for x in self.service.get_categories()
            if x["nombre"] == "Algodón"
        )
        self.service.remove_catalog_option("categorias", category_id)
        create_database(self.db)
        self.assertNotIn("Algodón",
                         [x["nombre"] for x in self.service.get_categories()])

    def test_duplicate_and_invalid_catalog_options(self):
        with self.assertRaises(ValueError):
            self.service.add_catalog_option("categorias", "algodón")
        with self.assertRaises(ValueError):
            self.service.add_catalog_option("unidades", "")
        with self.assertRaises(ValueError):
            self.service.add_catalog_option("unidades", "A" * 81)
        with self.assertRaises(ValueError):
            self.service.add_catalog_option("productos", "Nombre")

    def test_existing_unit_names_are_migrated(self):
        self.db.cursor().execute(
            """INSERT INTO productos (codigo, nombre, unidad)
               VALUES ('PRUEBA-LEGACY', 'Producto anterior', 'carrete')"""
        )
        self.db.commit()
        create_database(self.db)
        self.assertIn("carrete", [x["nombre"] for x in self.service.get_units()])


if __name__ == "__main__":
    unittest.main()
