import unittest
from pathlib import Path


class SaleHistoryUiContractTest(unittest.TestCase):
    def test_tree_widget_uses_supported_pyside6_methods(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "ui"
            / "sale_history_window.py"
        ).read_text(encoding="utf-8")

        self.assertIn("self.tabla.setHeaderLabels(", source)
        self.assertNotIn("self.tabla.setHorizontalHeaderLabels(", source)
        self.assertNotIn("self.tabla.setFirstItemColumnSpanned(", source)
        self.assertIn("year_item.setFirstColumnSpanned(True)", source)
        self.assertIn("month_item.setFirstColumnSpanned(True)", source)


if __name__ == "__main__":
    unittest.main()
