from datetime import datetime
from typing import Optional

from app.database.connection import Database


class SaleService:
    """Operaciones de negocio relacionadas con ventas."""

    PAYMENT_METHODS = (
        "Efectivo",
        "Transferencia",
        "Mercado Libre",
    )

    def __init__(self, database: Database) -> None:
        self.database = database

    def find_product(self, code: str) -> Optional[dict]:
        """Busca un producto activo por código interno o código de barras."""
        code = code.strip()

        if not code:
            return None

        cursor = self.database.cursor()
        cursor.execute(
            """
            SELECT
                p.id,
                p.codigo,
                p.codigo_barras,
                p.codigo_qr,
                p.nombre,
                p.unidad,
                p.precio,
                p.existencia,
                p.stock_minimo,
                COALESCE(c.nombre, '') AS categoria,
                COALESCE(p.marca, '') AS marca,
                COALESCE(p.color, '') AS color
            FROM productos p
            LEFT JOIN categorias c
                ON c.id = p.categoria_id
            WHERE p.activo = 1
              AND (
                  p.codigo = ?
                  OR p.codigo_barras = ?
                  OR p.codigo_qr = ?
              )
            LIMIT 1
            """,
            (code, code, code),
        )

        row = cursor.fetchone()

        return dict(row) if row else None

    def search_products(self, query: str, limit: int = 20) -> list[dict]:
        """Busca coincidencias para la captura predictiva de ventas."""

        query = query.strip()
        if not query:
            return []
        pattern = f"%{query}%"
        cursor = self.database.cursor()
        cursor.execute(
            """
            SELECT
                p.id, p.codigo, p.codigo_barras, p.codigo_qr, p.nombre,
                p.precio, p.existencia, p.stock_minimo,
                COALESCE(p.marca, '') AS marca,
                COALESCE(p.color, '') AS color,
                COALESCE(c.nombre, '') AS categoria
            FROM productos p
            LEFT JOIN categorias c ON c.id = p.categoria_id
            WHERE p.activo = 1
              AND (
                  p.codigo LIKE ?
                  OR COALESCE(p.codigo_barras, '') LIKE ?
                  OR COALESCE(p.codigo_qr, '') LIKE ?
                  OR p.nombre LIKE ?
                  OR COALESCE(p.marca, '') LIKE ?
              )
            ORDER BY
                CASE
                    WHEN p.codigo = ? OR p.codigo_barras = ?
                         OR p.codigo_qr = ? THEN 0
                    WHEN p.nombre LIKE ? THEN 1
                    ELSE 2
                END,
                p.nombre COLLATE NOCASE
            LIMIT ?
            """,
            (
                pattern, pattern, pattern, pattern, pattern,
                query, query, query, f"{query}%", int(limit),
            ),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_commission_rate(self) -> float:
        """Obtiene la comisión configurada para Mercado Libre."""
        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT valor
            FROM configuracion
            WHERE clave = 'comision_mercado_libre'
            """
        )

        row = cursor.fetchone()

        if not row:
            return 4.0

        try:
            return float(row[0])
        except (TypeError, ValueError):
            return 4.0

    def create_sale(
        self,
        items: list[dict],
        payment_method: str | None = None,
        discount: float = 0.0,
        user_id: Optional[int] = None,
    ) -> dict:
        """
        Registra una venta completa.

        items debe contener:
            producto_id
            cantidad
            precio_unitario
        """

        if not items:
            raise ValueError("La venta no contiene productos.")

        discount = float(discount or 0)

        if discount < 0:
            raise ValueError("El descuento no puede ser negativo.")

        subtotal = sum(
            float(item["cantidad"]) * float(item["precio_unitario"])
            for item in items
        )

        if discount > subtotal:
            raise ValueError(
                "El descuento no puede superar el subtotal."
            )

        total = round(subtotal - discount, 2)
        default_method = payment_method or "Efectivo"
        commission_rate = self.get_commission_rate()
        prepared_items = []
        allocated_discount = 0.0
        for index, item in enumerate(items):
            method = item.get("metodo_pago") or default_method
            if method not in self.PAYMENT_METHODS:
                raise ValueError("El método de pago no es válido.")
            line_subtotal = round(
                float(item["cantidad"]) * float(item["precio_unitario"]), 2
            )
            if index == len(items) - 1:
                line_discount = round(discount - allocated_discount, 2)
            elif subtotal:
                line_discount = round(
                    discount * line_subtotal / subtotal, 2
                )
                allocated_discount += line_discount
            else:
                line_discount = 0.0
            line_total = round(line_subtotal - line_discount, 2)
            rate = commission_rate if method == "Mercado Libre" else 0.0
            line_commission = round(line_total * rate / 100, 2)
            prepared_items.append({
                **item,
                "metodo_pago": method,
                "subtotal": line_subtotal,
                "descuento": line_discount,
                "porcentaje_comision": rate,
                "monto_comision": line_commission,
                "total_neto": round(line_total - line_commission, 2),
            })

        methods = {item["metodo_pago"] for item in prepared_items}
        sale_payment_method = methods.pop() if len(methods) == 1 else "Mixto"
        commission = round(
            sum(item["monto_comision"] for item in prepared_items), 2
        )
        total_net = round(total - commission, 2)
        sale_commission_rate = round(
            (commission / total * 100) if total > 0 else 0.0,
            4,
        )

        now = datetime.now()

        fecha = now.strftime("%Y-%m-%d")
        hora = now.strftime("%H:%M:%S")

        folio = self._next_folio(fecha)

        cursor = self.database.cursor()

        try:
            cursor.execute("BEGIN")

            # Validamos existencia antes de modificar cualquier dato.
            for item in items:
                product_id = int(item["producto_id"])
                quantity = float(item["cantidad"])

                if quantity <= 0:
                    raise ValueError(
                        "La cantidad debe ser mayor que cero."
                    )

                cursor.execute(
                    """
                    SELECT nombre, existencia
                    FROM productos
                    WHERE id = ?
                      AND activo = 1
                    """,
                    (product_id,),
                )

                product = cursor.fetchone()

                if not product:
                    raise ValueError(
                        "Uno de los productos ya no está disponible."
                    )

                existencia = float(product["existencia"])

                if existencia < quantity:
                    raise ValueError(
                        f"Existencia insuficiente para "
                        f"'{product['nombre']}'. "
                        f"Disponible: {existencia:g}."
                    )

            # Cabecera de la venta.
            cursor.execute(
                """
                INSERT INTO ventas (
                    folio,
                    fecha,
                    hora,
                    subtotal,
                    descuento,
                    total,
                    metodo_pago,
                    porcentaje_comision,
                    monto_comision,
                    total_neto,
                    usuario_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    folio,
                    fecha,
                    hora,
                    subtotal,
                    discount,
                    total,
                    sale_payment_method,
                    sale_commission_rate,
                    commission,
                    total_net,
                    user_id,
                ),
            )

            sale_id = int(cursor.lastrowid)

            # Detalle + actualización de inventario.
            for item in prepared_items:
                product_id = int(item["producto_id"])
                quantity = float(item["cantidad"])
                unit_price = float(item["precio_unitario"])

                line_subtotal = item["subtotal"]

                cursor.execute(
                    """
                    SELECT costo
                    FROM productos
                    WHERE id = ?
                    """,
                    (product_id,),
                    )
                
                product_cost = float(
                    cursor.fetchone()["costo"]
                    )
                cursor.execute(
                    """
                    INSERT INTO detalle_venta (
                        venta_id,
                        producto_id,
                        cantidad,
                        precio_unitario,
                        costo_unitario,
                        descuento,
                        subtotal,
                        metodo_pago,
                        porcentaje_comision,
                        monto_comision,
                        total_neto
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                    (
                        sale_id,
                        product_id,
                        quantity,
                        unit_price,
                        product_cost,
                        item["descuento"],
                        line_subtotal,
                        item["metodo_pago"],
                        item["porcentaje_comision"],
                        item["monto_comision"],
                        item["total_neto"],
                        ),
                    )

                cursor.execute(
                    """
                    SELECT existencia
                    FROM productos
                    WHERE id = ?
                    """,
                    (product_id,),
                )

                previous_stock = float(
                    cursor.fetchone()["existencia"]
                )

                new_stock = previous_stock - quantity

                cursor.execute(
                    """
                    UPDATE productos
                    SET
                        existencia = ?,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        new_stock,
                        product_id,
                    ),
                )

                cursor.execute(
                    """
                    INSERT INTO movimientos_inventario (
                        producto_id,
                        tipo,
                        cantidad,
                        existencia_anterior,
                        existencia_nueva,
                        referencia,
                        usuario_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_id,
                        "VENTA",
                        -quantity,
                        previous_stock,
                        new_stock,
                        folio,
                        user_id,
                    ),
                )

            self.database.commit()

        except Exception:
            self.database.rollback()
            raise

        return {
            "id": sale_id,
            "folio": folio,
            "fecha": fecha,
            "hora": hora,
            "subtotal": round(subtotal, 2),
            "descuento": round(discount, 2),
            "total": total,
            "metodo_pago": sale_payment_method,
            "porcentaje_comision": sale_commission_rate,
            "monto_comision": commission,
            "total_neto": total_net,
        }

    def _next_folio(self, fecha: str) -> str:
        """Genera un folio consecutivo para el día."""
        prefix = f"V-{fecha.replace('-', '')}-"

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT folio
            FROM ventas
            WHERE folio LIKE ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (f"{prefix}%",),
        )

        row = cursor.fetchone()

        if not row:
            sequence = 1
        else:
            try:
                sequence = (
                    int(str(row["folio"]).split("-")[-1])
                    + 1
                )
            except (ValueError, IndexError):
                sequence = 1

        return f"{prefix}{sequence:04d}"
