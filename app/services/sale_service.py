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
                p.nombre,
                p.unidad,
                p.precio,
                p.existencia,
                p.stock_minimo,
                COALESCE(c.nombre, '') AS categoria,
                COALESCE(p.marca, '') AS marca
            FROM productos p
            LEFT JOIN categorias c
                ON c.id = p.categoria_id
            WHERE p.activo = 1
              AND (
                  p.codigo = ?
                  OR p.codigo_barras = ?
              )
            LIMIT 1
            """,
            (code, code),
        )

        row = cursor.fetchone()

        return dict(row) if row else None

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
        payment_method: str,
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

        if payment_method not in self.PAYMENT_METHODS:
            raise ValueError("El método de pago no es válido.")

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

        if payment_method == "Mercado Libre":
            commission_rate = self.get_commission_rate()
        else:
            commission_rate = 0.0

        commission = round(
            total * commission_rate / 100,
            2,
        )

        total_net = round(
            total - commission,
            2,
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
                    payment_method,
                    commission_rate,
                    commission,
                    total_net,
                    user_id,
                ),
            )

            sale_id = int(cursor.lastrowid)

            # Detalle + actualización de inventario.
            for item in items:
                product_id = int(item["producto_id"])
                quantity = float(item["cantidad"])
                unit_price = float(item["precio_unitario"])

                line_subtotal = round(
                    quantity * unit_price,
                    2,
                )

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
                        subtotal
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                    (
                        sale_id,
                        product_id,
                        quantity,
                        unit_price,
                        product_cost,
                        0,
                        line_subtotal,
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
            "metodo_pago": payment_method,
            "porcentaje_comision": commission_rate,
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