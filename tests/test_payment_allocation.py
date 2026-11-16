import unittest

from app.services.payment_allocation import calculate_payment, calculate_payment_from_received


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
            (350, {"Transferencia": 351}, 0),
            (350, {"Efectivo": -1, "Transferencia": 351}, 0),
            (350, {"Efectivo": 50.001, "Transferencia": 299.999}, 51),
        ]
        for total, payments, received in scenarios:
            with self.subTest(payments=payments, received=received):
                with self.assertRaises(ValueError):
                    calculate_payment(total, payments, received)

    def test_derive_cash_allocation_only_from_total_and_electronic_payments(self):
        result = calculate_payment_from_received(
            total=350, transfer=100, card=200, cash_received=100,
            commission_percentage=4,
        )
        self.assertEqual(result["payments"], {
            "Efectivo": 50, "Transferencia": 100, "Mercado Libre": 200,
        })
        self.assertEqual(result["cash_received"], 100)
        self.assertEqual(result["change"], 50)
        self.assertEqual(result["commission"], 8)
        self.assertEqual(result["net_total"], 342)

    def test_derive_cash_only_and_electronic_only(self):
        cash = calculate_payment_from_received(85, cash_received=100)
        self.assertEqual(cash["payments"]["Efectivo"], 85)
        self.assertEqual(cash["change"], 15)
        transfer = calculate_payment_from_received(
            350, transfer=350, cash_received=0
        )
        self.assertEqual(transfer["payments"]["Efectivo"], 0)
        self.assertEqual(transfer["payment_method"], "Transferencia")
        self.assertEqual(transfer["change"], 0)

    def test_cash_hand_back_when_electronic_already_covers_sale(self):
        result = calculate_payment_from_received(
            350, transfer=350, cash_received=100
        )
        self.assertEqual(result["payments"]["Efectivo"], 0)
        self.assertEqual(result["cash_received"], 100)
        self.assertEqual(result["change"], 100)

    def test_automatic_cash_allocation_rejects_partial_or_overfull_payment(self):
        for allocation in (
            {"total": 350, "transfer": 100, "card": 200, "cash_received": 49},
            {"total": 350, "transfer": 300, "card": 100, "cash_received": 0},
            {"total": 350, "cash_received": -1},
            {"total": 350, "cash_received": 350.001},
            {"total": 350, "card": 1.001, "cash_received": 349},
        ):
            with self.subTest(allocation=allocation):
                with self.assertRaises(ValueError):
                    calculate_payment_from_received(**allocation)

    def test_card_commission_only_applies_to_card_amount(self):
        result = calculate_payment(
            350, {"Efectivo": 50, "Transferencia": 100, "Mercado Libre": 200},
            50, 4,
        )
        self.assertEqual(result["commission"], 8)


if __name__ == "__main__":
    unittest.main()
