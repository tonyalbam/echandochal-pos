"""Pruebas de etiquetas por lotes, sin acceder a la BD de producción."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from app.database.schema import create_database
from app.services.label_service import LabelService


class MemoryDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        return self.connection.commit()


class BatchLabelTest(unittest.TestCase):
    def setUp(self):
        self.db = MemoryDatabase()
        create_database(self.db)
        self.db.cursor().executemany(
            """INSERT INTO productos (
                 codigo, codigo_barras, codigo_qr, nombre, color, existencia
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            [
                ("ECH0000001", "123456789101", "QR-A", "Estambre Uno", "Azul", 5),
                ("ECH0000002", None, None, "Estambre Dos", "Rojo", 10),
                ("ECH0000003", None, None, "Estambre Tres", None, 20),
            ],
        )
        self.db.commit()
        self.service = LabelService(self.db)

    def tearDown(self):
        self.db.connection.close()

    def test_pdf_multiple_products_and_color(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.service.generate_product_labels(
                [1, 2, 3], Path(temp) / "batch.pdf", "Ambos", "PDF"
            )
            self.assertTrue(path.exists())
            reader = PdfReader(str(path))
            self.assertEqual(len(reader.pages), 1)
            text = reader.pages[0].extract_text()
            for expected in ("Estambre Uno", "Color: Azul", "Estambre Dos",
                             "Color: Rojo", "Color: Sin especificar"):
                self.assertIn(expected, text)

    def test_pdf_pagination(self):
        ids = []
        for n in range(4, 13):
            cursor = self.db.cursor()
            cursor.execute(
                "INSERT INTO productos (codigo, nombre, color) VALUES (?, ?, ?)",
                (f"ECH{n:07}", f"Producto {n}", "Verde"),
            )
            ids.append(cursor.lastrowid)
        self.db.commit()
        with tempfile.TemporaryDirectory() as temp:
            path = self.service.generate_product_labels(
                [1, 2, 3] + ids, Path(temp) / "many.pdf",
                "Código de barras", "PDF"
            )
            self.assertEqual(len(PdfReader(str(path)).pages), 2)

    def test_editable_word_with_embedded_images(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.service.generate_product_labels(
                [1, 2], Path(temp) / "labels.docx", "Ambos", "Word (.docx)"
            )
            doc = Document(path)
            self.assertEqual(len(doc.tables), 1)
            text = "\n".join(cell.text for row in doc.tables[0].rows for cell in row.cells)
            self.assertIn("Estambre Uno", text)
            self.assertIn("Color: Azul", text)
            self.assertIn("Color: Rojo", text)
            self.assertGreaterEqual(len(doc.inline_shapes), 4)

    def test_reject_empty_or_duplicate_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            for ids in ([], [1, 1]):
                with self.subTest(ids=ids):
                    with self.assertRaises(ValueError):
                        self.service.generate_product_labels(
                            ids, Path(temp) / "invalid.pdf"
                        )

    def test_no_database_mutations(self):
        before = [tuple(row) for row in self.db.cursor().execute(
            "SELECT codigo, codigo_barras, codigo_qr, nombre, color, existencia FROM productos ORDER BY id"
        )]
        with tempfile.TemporaryDirectory() as temp:
            self.service.generate_product_labels(
                [1, 2], Path(temp) / "batch.pdf", "Ambos"
            )
        after = [tuple(row) for row in self.db.cursor().execute(
            "SELECT codigo, codigo_barras, codigo_qr, nombre, color, existencia FROM productos ORDER BY id"
        )]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
