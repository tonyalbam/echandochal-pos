import sqlite3
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from app.database.schema import create_database
from app.services.configuration_service import ConfigurationService
from app.services.sale_service import SaleService
from app.services.ticket_service import TicketService


class MemoryDatabase:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def cursor(self) -> sqlite3.Cursor:
        return self.connection.cursor()

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


class TicketServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MemoryDatabase()
        create_database(self.database)
        ConfigurationService(self.database).update_settings(
            "Boutique Prueba",
            4,
        )

        cursor = self.database.cursor()
        cursor.execute(
            """
            INSERT INTO productos (
                codigo, nombre, costo, precio, existencia
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "P-1",
                "Producto de nombre suficientemente largo para ticket",
                50,
                85,
                10,
            ),
        )
        product_id = int(cursor.lastrowid)
        self.database.commit()
        self.sale = SaleService(self.database).create_sale(
            items=[
                {
                    "producto_id": product_id,
                    "cantidad": 2,
                    "precio_unitario": 85,
                }
            ],
            payment_method="Mercado Libre",
            discount=10,
        )

    def tearDown(self) -> None:
        self.database.close()

    def test_ticket_pdf_contains_sale_information(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = TicketService(
                self.database
            ).generate_sale_ticket(
                self.sale["id"],
                Path(directory) / "ticket",
            )

            self.assertEqual(output_path.suffix, ".pdf")
            self.assertTrue(output_path.exists())

            reader = PdfReader(output_path)
            self.assertEqual(len(reader.pages), 1)
            text = reader.pages[0].extract_text()

            self.assertIn("Boutique Prueba", text)
            self.assertIn(self.sale["folio"], text)
            self.assertIn("Producto de nombre", text)
            self.assertIn("Mercado Libre", text)
            self.assertIn("$160.00", text)
            self.assertNotIn("Comision", text)
            self.assertNotIn("$6.40", text)

            resources = reader.pages[0]["/Resources"]
            self.assertIn("/XObject", resources)
            self.assertGreater(len(resources["/XObject"]), 0)

    def test_cancelled_sale_ticket_shows_status(self) -> None:
        self.database.connection.execute(
            "UPDATE ventas SET cancelada = 1 WHERE id = ?",
            (self.sale["id"],),
        )
        self.database.commit()

        with tempfile.TemporaryDirectory() as directory:
            output_path = TicketService(
                self.database
            ).generate_sale_ticket(
                self.sale["id"],
                Path(directory) / "cancelado.pdf",
            )

            text = PdfReader(output_path).pages[0].extract_text()
            self.assertIn("VENTA CANCELADA", text)

    def test_missing_sale_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TicketService(self.database).generate_sale_ticket(
                99999,
                "ticket.pdf",
            )


if __name__ == "__main__":
    unittest.main()
