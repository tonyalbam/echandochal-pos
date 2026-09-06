def group_sale_items(items: list[dict]) -> tuple[list[dict], bool]:
    """Agrupa por producto y avisa si se unificaron formas de pago distintas."""
    grouped: dict[int, dict] = {}
    had_mixed_payments = False
    for item in items:
        product_id = int(item["producto_id"])
        if product_id not in grouped:
            grouped[product_id] = dict(item)
            continue
        if grouped[product_id]["metodo_pago"] != item["metodo_pago"]:
            had_mixed_payments = True
        grouped[product_id]["cantidad"] += float(item["cantidad"])
    return list(grouped.values()), had_mixed_payments


def expand_sale_items(items: list[dict]) -> list[dict]:
    """Convierte cantidades enteras en partidas unitarias independientes."""
    expanded = []
    for item in items:
        quantity = float(item["cantidad"])
        whole_units = int(quantity)
        for _ in range(whole_units):
            unit = dict(item)
            unit["cantidad"] = 1.0
            expanded.append(unit)
        remainder = round(quantity - whole_units, 6)
        if remainder:
            unit = dict(item)
            unit["cantidad"] = remainder
            expanded.append(unit)
    return expanded


def calculate_discount(subtotal: float, value: float, mode: str) -> float:
    """Devuelve el importe monetario de un descuento fijo o porcentual."""
    if mode == "Porcentaje":
        return round(float(subtotal) * float(value) / 100, 2)
    return round(float(value), 2)
