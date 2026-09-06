import unittest
from pathlib import Path


class CashClosingUiContractTest(unittest.TestCase):
    def test_loose_change_field_clears_when_it_receives_focus(self) -> None:
        source = Path("app/ui/cash_closing_window.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("class ClearOnFocusDoubleSpinBox", source)
        self.assertIn("def focusInEvent(self, event)", source)
        self.assertIn("self.setValue(0)", source)
        self.assertIn(
            "self.loose_change = ClearOnFocusDoubleSpinBox()", source
        )


if __name__ == "__main__":
    unittest.main()
