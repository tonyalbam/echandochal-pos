def group_sale_items(items: list[dict]) -> tuple[list[dict], bool]:
    """Agrupa por producto y avisa si se unificaron formas de pago distintas."""
    grouped: dict[int, dict] = {}
    had_mixed_payments = False
    for item in items:
        product_id = int(item["producto_id"])
        if product_id not in grouped:
            grouped[product_id] = dict(item)
            continue
        if grouped[product_id].get("metodo_pago") != item.get("metodo_pago"):
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


def has_available_inventory(
    product_id: int,
    inventory: float,
    items: list[dict],
) -> bool:
    """Indica si todavía puede agregarse una unidad al carrito."""
    quantity_in_cart = sum(
        float(item["cantidad"])
        for item in items
        if int(item["producto_id"]) == int(product_id)
    )
    return quantity_in_cart + 1 <= float(inventory)


def adjusted_sale_quantity(
    items: list[dict],
    row: int,
    change: float,
    inventory: float,
) -> float:
    """Calcula una nueva cantidad sin rebasar el inventario del producto.

    change es el ajuste (positivo para agregar, negativo para quitar).
    Las demás líneas del mismo producto también cuentan contra el stock.
    Retorna 0 cuando la fila debe eliminarse. No modifica items.
    """
    from math import isfinite

    if not 0 <= row < len(items):
        raise ValueError("Selecciona un producto de la venta.")

    change = float(change)
    inventory = float(inventory)
    if not isfinite(change) or not isfinite(inventory) or abs(change) < 0.0000001:
        raise ValueError("Ingresa una cantidad válida para agregar o quitar.")

    current = float(items[row]["cantidad"])
    new_quantity = round(current + change, 6)
    if new_quantity < 0:
        raise ValueError(
            f"No es posible quitar más de {current:g} unidades de esta fila."
        )

    if change > 0:
        product_id = int(items[row]["producto_id"])
        in_cart = sum(
            float(item["cantidad"])
            for item in items
            if int(item["producto_id"]) == product_id
        )
        if round(in_cart + change, 6) > inventory + 0.0000001:
            free = max(0.0, round(inventory - in_cart, 6))
            raise ValueError(
                f"¡Ya no hay inventario suficiente! "
                f"Disponible para agregar: {free:g}. "
                f"Existencia total: {inventory:g}; en el carrito: {in_cart:g}."
            )

    return max(0.0, new_quantity)
