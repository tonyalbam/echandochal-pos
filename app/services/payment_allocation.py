"""Cobro por venta completa; importes monetarios exactos en centavos."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

PAYMENT_METHODS = ("Efectivo", "Transferencia", "Mercado Libre")


def cents(value: object) -> int:
    """Convierte un importe no negativo a centavos, sin redondear silenciosamente."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("El importe debe ser numerico.") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("El importe debe ser finito y no negativo.")
    amount = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount != number:
        raise ValueError("El importe no puede tener mas de dos decimales.")
    return int(amount * 100)


def calculate_payment(total: object, allocations: dict[str, object],
                      cash_received: object = 0,
                      commission_percentage: object = 0) -> dict:
    """Valida pagos mixtos; el cambio no se contabiliza como ingreso.

    allocations contiene los importes aplicados a la venta, no los billetes
    recibidos. cash_received corresponde al efectivo entregado por el cliente.
    """
    total_cents = cents(total)
    if total_cents <= 0:
        raise ValueError("La venta debe tener un total mayor que cero.")
    unknown = set(allocations) - set(PAYMENT_METHODS)
    if unknown:
        raise ValueError("Hay una forma de pago desconocida.")
    amounts = {method: cents(allocations.get(method, 0))
               for method in PAYMENT_METHODS}
    if sum(amounts.values()) != total_cents:
        raise ValueError("La suma de las formas de pago debe ser igual al total.")
    received = cents(cash_received)
    if received < amounts["Efectivo"]:
        raise ValueError("El efectivo recibido es insuficiente.")
    if not amounts["Efectivo"] and received:
        raise ValueError("No se puede recibir efectivo en una venta sin pago en efectivo.")
    change = received - amounts["Efectivo"]
    rate = Decimal(str(commission_percentage))
    if not rate.is_finite() or rate < 0 or rate > 100:
        raise ValueError("La comision debe estar entre 0 y 100.")
    commission_cents = int(
        (Decimal(amounts["Mercado Libre"]) * rate / 100)
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    active_methods = [method for method, amount in amounts.items() if amount]
    return {
        "total": total_cents / 100,
        "payments": {method: amount / 100 for method, amount in amounts.items()},
        "cash_received": received / 100,
        "change": change / 100,
        "payment_method": active_methods[0] if len(active_methods) == 1 else "Mixto",
        "commission": commission_cents / 100,
        "net_total": (total_cents - commission_cents) / 100,
    }
