import unittest
from pathlib import Path


class ProductDialogUiContractTest(unittest.TestCase):
    def test_internal_code_is_prefilled_and_read_only(self) -> None:
        source = Path("app/ui/product_dialog.py").read_text(encoding="utf-8")

        self.assertIn("self.codigo.setReadOnly(True)", source)
        self.assertIn("self.product_service.get_next_internal_code()", source)


if __name__ == "__main__":
    unittest.main()
