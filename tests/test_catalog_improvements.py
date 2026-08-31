import sqlite3
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from app.database.schema import create_database
from app.services.product_service import ProductService
from app.services.sale_service import SaleService
from app.services.supplier_service import SupplierService
from app.services.label_service import LabelService


class MemoryDatabase:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def cursor(self):
        return self.connection.cursor()

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


class CatalogImprovementsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MemoryDatabase()
        create_database(self.database)

    def tearDown(self) -> None:
        self.database.close()

    def test_required_categories_are_available_in_defined_order(self) -> None:
        categories = ProductService(self.database).get_categories()
        self.assertEqual(
            [category["nombre"] for category in categories],
            list(ProductService.ALLOWED_CATEGORIES),
        )

    def test_sale_search_matches_code_barcode_name_and_brand(self) -> None:
        cursor = self.database.cursor()
        cursor.execute(
            """
            INSERT INTO productos (
                codigo, codigo_barras, codigo_qr, nombre, marca, color,
                costo, precio, existencia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ALG-001", "750123456", "QR-FABRICA-001",
                "Estambre Primavera", "Nube", "Azul", 20, 45, 8,
            ),
        )
        self.database.commit()
        service = SaleService(self.database)
        for query in ("ALG", "750123", "QR-FABRICA", "Primavera", "Nube"):
            matches = service.search_products(query)
            self.assertEqual(matches[0]["codigo"], "ALG-001")
            self.assertEqual(matches[0]["color"], "Azul")
        self.assertEqual(
            service.find_product("QR-FABRICA-001")["codigo"], "ALG-001"
        )

    def test_generates_scannable_barcode_and_qr_label(self) -> None:
        cursor = self.database.cursor()
        cursor.execute(
            """
            INSERT INTO productos (
                codigo, nombre, marca, costo, precio, existencia
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("ECH-QR-01", "Producto con etiqueta", "Echando Chal", 10, 25, 4),
        )
        product_id = int(cursor.lastrowid)
        self.database.commit()
        with tempfile.TemporaryDirectory() as directory:
            output = LabelService(self.database).generate_product_label(
                product_id, Path(directory) / "etiqueta", "Ambos"
            )
            self.assertTrue(output.is_file())
            reader = PdfReader(output)
            self.assertEqual(len(reader.pages), 1)
            self.assertAlmostEqual(float(reader.pages[0].mediabox.width), 80 / 25.4 * 72, places=1)
            self.assertAlmostEqual(float(reader.pages[0].mediabox.height), 50 / 25.4 * 72, places=1)

    def test_supplier_crud_saves_name_address_and_phone(self) -> None:
        service = SupplierService(self.database)
        supplier_id = service.save_supplier(
            "Hilaturas Centro", "Calle Uno 51", "771 555 0101"
        )
        supplier = service.get_supplier(supplier_id)
        self.assertEqual(supplier["nombre"], "Hilaturas Centro")
        self.assertEqual(supplier["direccion"], "Calle Uno 51")
        self.assertEqual(supplier["telefono"], "771 555 0101")

        service.save_supplier(
            "Hilaturas Centro", "Avenida Dos 20", "771 555 0202",
            supplier_id,
        )
        updated = service.get_supplier(supplier_id)
        self.assertEqual(updated["direccion"], "Avenida Dos 20")
        self.assertEqual(len(service.list_suppliers("0202")), 1)

        service.deactivate_supplier(supplier_id)
        self.assertEqual(service.list_suppliers(), [])

    def test_duplicate_active_supplier_is_rejected(self) -> None:
        service = SupplierService(self.database)
        service.save_supplier("Proveedor Uno")
        with self.assertRaises(ValueError):
            service.save_supplier(" proveedor uno ")


if __name__ == "__main__":
    unittest.main()
