import unittest

from app.services.sale_cart_service import (
    calculate_discount,
    expand_sale_items,
    group_sale_items,
    has_available_inventory,
)


class SaleCartServiceTest(unittest.TestCase):
    def test_normal_mode_keeps_each_unit_as_a_separate_item(self) -> None:
        grouped = [{
            "producto_id": 1,
            "nombre": "Estambre",
            "cantidad": 3,
            "metodo_pago": "Transferencia",
        }]
        expanded = expand_sale_items(grouped)
        self.assertEqual(len(expanded), 3)
        self.assertEqual([item["cantidad"] for item in expanded], [1, 1, 1])
        self.assertTrue(all(
            item["metodo_pago"] == "Transferencia" for item in expanded
        ))

    def test_bulk_mode_groups_products_into_one_row(self) -> None:
        items = [
            {"producto_id": 1, "cantidad": 1, "metodo_pago": "Efectivo"},
            {"producto_id": 1, "cantidad": 1, "metodo_pago": "Efectivo"},
            {"producto_id": 2, "cantidad": 1, "metodo_pago": "Transferencia"},
        ]
        grouped, had_mixed_payments = group_sale_items(items)
        self.assertFalse(had_mixed_payments)
        self.assertEqual(len(grouped), 2)
        self.assertEqual(grouped[0]["cantidad"], 2)

    def test_bulk_mode_reports_unified_mixed_payments(self) -> None:
        items = [
            {"producto_id": 1, "cantidad": 1, "metodo_pago": "Efectivo"},
            {"producto_id": 1, "cantidad": 1, "metodo_pago": "Mercado Libre"},
        ]
        grouped, had_mixed_payments = group_sale_items(items)
        self.assertTrue(had_mixed_payments)
        self.assertEqual(grouped[0]["metodo_pago"], "Efectivo")
        self.assertEqual(grouped[0]["cantidad"], 2)

    def test_percentage_discount_returns_money_amount(self) -> None:
        self.assertEqual(calculate_discount(850, 10, "Porcentaje"), 85)
        self.assertEqual(calculate_discount(850, 85, "Monto"), 85)

    def test_inventory_accounts_for_units_already_in_cart(self) -> None:
        items = [
            {"producto_id": 1, "cantidad": 1},
            {"producto_id": 1, "cantidad": 1},
        ]
        self.assertFalse(has_available_inventory(1, 2, items))
        self.assertTrue(has_available_inventory(1, 3, items))

    def test_zero_inventory_is_never_available(self) -> None:
        self.assertFalse(has_available_inventory(1, 0, []))


if __name__ == "__main__":
    unittest.main()
