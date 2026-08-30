from app.database.connection import Database


class SaleHistoryService:
    """Consulta el historial, detalle y cancelación de ventas."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def list_sales(
        self,
        search: str = "",
        include_cancelled: bool = True,
    ) -> list[dict]:

        cursor = self.database.cursor()

        sql = """
            SELECT
                v.id,
                v.folio,
                v.fecha,
                v.hora,
                v.subtotal,
                v.descuento,
                v.total,
                v.metodo_pago,
                v.porcentaje_comision,
                v.monto_comision,
                v.total_neto,
                v.cancelada
            FROM ventas v
            WHERE 1 = 1
        """

        parameters: list = []

        if not include_cancelled:
            sql += " AND v.cancelada = 0"

        search = search.strip()

        if search:
            sql += """
                AND (
                    v.folio LIKE ?
                    OR v.metodo_pago LIKE ?
                )
            """

            pattern = f"%{search}%"
            parameters.extend([pattern, pattern])

        sql += """
            ORDER BY
                v.fecha DESC,
                v.hora DESC,
                v.id DESC
        """

        cursor.execute(sql, parameters)

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    def get_sale(
        self,
        sale_id: int,
    ) -> dict | None:

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT
                v.id,
                v.folio,
                v.fecha,
                v.hora,
                v.subtotal,
                v.descuento,
                v.total,
                v.metodo_pago,
                v.porcentaje_comision,
                v.monto_comision,
                v.total_neto,
                v.usuario_id,
                v.cancelada
            FROM ventas v
            WHERE v.id = ?
            """,
            (sale_id,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        sale = dict(row)

        cursor.execute(
            """
            SELECT
                dv.id,
                dv.producto_id,
                p.codigo,
                p.nombre,
                dv.cantidad,
                dv.precio_unitario,
                dv.descuento,
                dv.subtotal
            FROM detalle_venta dv
            INNER JOIN productos p
                ON p.id = dv.producto_id
            WHERE dv.venta_id = ?
            ORDER BY dv.id
            """,
            (sale_id,),
        )

        sale["items"] = [
            dict(item)
            for item in cursor.fetchall()
        ]

        return sale

    def cancel_sale(
        self,
        sale_id: int,
        usuario_id: int | None = None,
    ) -> dict:
        """Cancela una venta y devuelve sus productos al inventario."""

        cursor = self.database.cursor()

        try:
            cursor.execute(
                """
                SELECT
                    id,
                    folio,
                    cancelada
                FROM ventas
                WHERE id = ?
                """,
                (sale_id,),
            )

            venta = cursor.fetchone()

            if venta is None:
                raise ValueError(
                    "La venta no existe."
                )

            if venta["cancelada"]:
                raise ValueError(
                    "La venta ya está cancelada."
                )

            folio = venta["folio"]

            cursor.execute(
                """
                SELECT
                    dv.producto_id,
                    dv.cantidad,
                    p.nombre,
                    p.existencia
                FROM detalle_venta dv
                INNER JOIN productos p
                    ON p.id = dv.producto_id
                WHERE dv.venta_id = ?
                ORDER BY dv.id
                """,
                (sale_id,),
            )

            detalles = cursor.fetchall()

            if not detalles:
                raise ValueError(
                    "La venta no tiene productos asociados."
                )

            for detalle in detalles:
                producto_id = detalle["producto_id"]
                cantidad = float(detalle["cantidad"])

                existencia_anterior = float(
                    detalle["existencia"]
                )

                existencia_nueva = (
                    existencia_anterior + cantidad
                )

                cursor.execute(
                    """
                    UPDATE productos
                    SET
                        existencia = ?,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        existencia_nueva,
                        producto_id,
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
                        producto_id,
                        "DEVOLUCION_VENTA",
                        cantidad,
                        existencia_anterior,
                        existencia_nueva,
                        folio,
                        usuario_id,
                    ),
                )

            cursor.execute(
                """
                UPDATE ventas
                SET
                    cancelada = 1
                WHERE id = ?
                """,
                (sale_id,),
            )

            cursor.execute(
                """
                INSERT INTO auditoria (
                    usuario_id,
                    accion,
                    modulo,
                    referencia,
                    detalles
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    usuario_id,
                    "CANCELAR",
                    "VENTAS",
                    folio,
                    "Venta cancelada y mercancía devuelta al inventario.",
                ),
            )

            self.database.commit()

            return {
                "id": sale_id,
                "folio": folio,
                "productos_devueltos": len(detalles),
            }

        except Exception:
            self.database.rollback()
            raise