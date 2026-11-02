import unittest

from app.services.payment_allocation import calculate_payment


class PaymentAllocationTest(unittest.TestCase):
    def test_three_methods_and_change(self):
        result = calculate_payment(
            350, {"Efectivo": 50, "Transferencia": 100, "Mercado Libre": 200},
            cash_received=100, commission_percentage=4,
        )
        self.assertEqual(result["payment_method"], "Mixto")
        self.assertEqual(result["payments"], {
            "Efectivo": 50, "Transferencia": 100, "Mercado Libre": 200
        })
        self.assertEqual(result["change"], 50)
        self.assertEqual(result["commission"], 8)
        self.assertEqual(result["net_total"], 342)

    def test_cash_only_with_change(self):
        result = calculate_payment(85, {"Efectivo": 85}, cash_received=100)
        self.assertEqual(result["change"], 15)
        self.assertEqual(result["payments"]["Efectivo"], 85)

    def test_invalid_allocations_and_cash(self):
        scenarios = [
            (350, {"Efectivo": 50, "Transferencia": 100}, 50),
            (350, {"Efectivo": 50, "Transferencia": 100, "Mercado Libre": 201}, 50),
            (350, {"Efectivo": 50, "Transferencia": 100, "Mercado Libre": 200}, 49),
            (350, {"Transferencia": 350}, 10),
            (350, {"Efectivo": -1, "Transferencia": 351}, 0),
            (350, {"Efectivo": 50.001, "Transferencia": 299.999}, 51),
        ]
        for total, payments, received in scenarios:
            with self.subTest(payments=payments, received=received):
                with self.assertRaises(ValueError):
                    calculate_payment(total, payments, received)

    def test_card_commission_only_applies_to_card_amount(self):
        result = calculate_payment(
            350, {"Efectivo": 50, "Transferencia": 100, "Mercado Libre": 200},
            50, 4,
        )
        self.assertEqual(result["commission"], 8)


if __name__ == "__main__":
    unittest.main()
