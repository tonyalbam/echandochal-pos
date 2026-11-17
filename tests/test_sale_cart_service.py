import unittest

from app.services.sale_cart_service import (
    adjusted_sale_quantity,
    set_sale_quantity,
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

    def test_quantity_adjustment_adds_and_subtracts_without_mutation(self) -> None:
        items = [{"producto_id": 1, "cantidad": 2}]
        self.assertEqual(adjusted_sale_quantity(items, 0, 3, 5), 5)
        self.assertEqual(adjusted_sale_quantity(items, 0, -1, 5), 1)
        self.assertEqual(adjusted_sale_quantity(items, 0, -2, 5), 0)
        self.assertEqual(items[0]["cantidad"], 2)

    def test_quantity_adjustment_counts_other_rows_of_same_product(self) -> None:
        items = [
            {"producto_id": 1, "cantidad": 2},
            {"producto_id": 1, "cantidad": 2},
            {"producto_id": 2, "cantidad": 100},
        ]
        self.assertEqual(adjusted_sale_quantity(items, 0, 1, 5), 3)
        with self.assertRaisesRegex(ValueError, "inventario"):
            adjusted_sale_quantity(items, 0, 2, 5)

    def test_quantity_adjustment_rejects_removing_more_than_row(self) -> None:
        items = [{"producto_id": 1, "cantidad": 1}]
        with self.assertRaisesRegex(ValueError, "quitar más"):
            adjusted_sale_quantity(items, 0, -2, 10)

    def test_quantity_adjustment_supports_fractional_products(self) -> None:
        items = [{"producto_id": 1, "cantidad": 0.75}]
        self.assertEqual(adjusted_sale_quantity(items, 0, 0.25, 1), 1)
        self.assertEqual(adjusted_sale_quantity(items, 0, -0.25, 1), 0.5)

    def test_quantity_adjustment_rejects_invalid_changes(self) -> None:
        items = [{"producto_id": 1, "cantidad": 1}]
        for change in (0, float("nan"), float("inf")):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    adjusted_sale_quantity(items, 0, change, 5)


    def test_absolute_quantity_sets_total_not_a_delta(self):
        items = [{"producto_id": 1, "cantidad": 2}]
        self.assertEqual(set_sale_quantity(items, 0, 5, 5), 5)
        self.assertEqual(set_sale_quantity(items, 0, 1, 5), 1)
        self.assertEqual(set_sale_quantity(items, 0, 0, 5), 0)
        self.assertEqual(set_sale_quantity(items, 0, 2, 5), 2)
        self.assertEqual(items[0]["cantidad"], 2)

    def test_absolute_quantity_counts_same_product_other_rows(self):
        items = [
            {"producto_id": 1, "cantidad": 1},
            {"producto_id": 1, "cantidad": 2},
            {"producto_id": 2, "cantidad": 50},
        ]
        self.assertEqual(set_sale_quantity(items, 0, 3, 5), 3)
        with self.assertRaisesRegex(ValueError, "Inventario insuficiente"):
            set_sale_quantity(items, 0, 4, 5)

    def test_absolute_quantity_allows_decrease_when_stock_dropped(self):
        items = [
            {"producto_id": 1, "cantidad": 4},
            {"producto_id": 1, "cantidad": 4},
        ]
        self.assertEqual(set_sale_quantity(items, 0, 2, 5), 2)
        self.assertEqual(set_sale_quantity(items, 0, 0, 5), 0)

    def test_absolute_quantity_rejects_decimals_and_negative(self):
        items = [{"producto_id": 1, "cantidad": 1}]
        for value in (1.5, -1, True, 1000000, None, "2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                set_sale_quantity(items, 0, value, 5)


if __name__ == "__main__":
    unittest.main()
