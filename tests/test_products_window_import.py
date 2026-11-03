"""Detecta errores de importación de la pantalla Productos en el arranque."""
import unittest


class ProductsWindowImportTest(unittest.TestCase):
    def test_products_window_imports(self):
        from app.ui.products_window import ProductsWindow
        from PySide6.QtGui import QShortcut
        self.assertIsNotNone(ProductsWindow)
        self.assertIsNotNone(QShortcut)


if __name__ == "__main__":
    unittest.main()
