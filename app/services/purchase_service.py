from datetime import datetime
from typing import Optional

from app.database.connection import Database


class PurchaseService:
    """Operaciones de negocio relacionadas con compras."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create_purchase(
        self,
        items: list[dict],
        supplier_id: Optional[int] = None,
        notes: str = "",
        user_id: Optional[int] = None,
    ) -> dict:
        """
        Registra una compra completa.

        items debe contener:
            producto_id
            cantidad
            costo_unitario
        """

        if not items:
            raise ValueError(
                "La compra no contiene productos."
            )

        subtotal = 0.0

        for item in items:
            quantity = float(item["cantidad"])
            unit_cost = float(item["costo_unitario"])

            if quantity <= 0:
                raise ValueError(
                    "La cantidad debe ser mayor que cero."
                )

            if unit_cost < 0:
                raise ValueError(
                    "El costo no puede ser negativo."
                )

            subtotal += quantity * unit_cost

        subtotal = round(subtotal, 2)
        total = subtotal

        now = datetime.now()

        fecha = now.strftime("%Y-%m-%d")
        folio = self._next_folio(fecha)

        cursor = self.database.cursor()

        try:
            cursor.execute("BEGIN")

            # Validamos todos los productos antes de modificar datos.
            for item in items:
                product_id = int(item["producto_id"])

                cursor.execute(
                    """
                    SELECT id, nombre, existencia, activo
                    FROM productos
                    WHERE id = ?
                    """,
                    (product_id,),
                )

                product = cursor.fetchone()

                if not product:
                    raise ValueError(
                        f"El producto con ID {product_id} no existe."
                    )

                if not product["activo"]:
                    raise ValueError(
                        f"El producto '{product['nombre']}' está inactivo."
                    )

            # Cabecera de la compra.
            cursor.execute(
                """
                INSERT INTO compras (
                    folio,
                    proveedor_id,
                    fecha,
                    subtotal,
                    total,
                    notas,
                    usuario_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    folio,
                    supplier_id,
                    fecha,
                    subtotal,
                    total,
                    notes,
                    user_id,
                ),
            )

            purchase_id = int(cursor.lastrowid)

            # Detalle + actualización del inventario.
            for item in items:
                product_id = int(item["producto_id"])
                quantity = float(item["cantidad"])
                unit_cost = float(item["costo_unitario"])

                line_subtotal = round(
                    quantity * unit_cost,
                    2,
                )

                cursor.execute(
                    """
                    INSERT INTO detalle_compra (
                        compra_id,
                        producto_id,
                        cantidad,
                        costo_unitario,
                        subtotal
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        purchase_id,
                        product_id,
                        quantity,
                        unit_cost,
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

                new_stock = previous_stock + quantity

                cursor.execute(
                    """
                    UPDATE productos
                    SET
                        existencia = ?,
                        costo = ?,
                        fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        new_stock,
                        unit_cost,
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
                        "COMPRA",
                        quantity,
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
            "id": purchase_id,
            "folio": folio,
            "fecha": fecha,
            "subtotal": subtotal,
            "total": total,
            "proveedor_id": supplier_id,
            "notas": notes,
        }

    def get_purchase(
        self,
        purchase_id: int,
    ) -> dict | None:
        """Obtiene una compra con su detalle."""

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT
                c.id,
                c.folio,
                c.proveedor_id,
                c.fecha,
                c.subtotal,
                c.total,
                c.notas,
                c.usuario_id
            FROM compras c
            WHERE c.id = ?
            """,
            (purchase_id,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        purchase = dict(row)

        cursor.execute(
            """
            SELECT
                dc.id,
                dc.producto_id,
                p.codigo,
                p.nombre,
                dc.cantidad,
                dc.costo_unitario,
                dc.subtotal
            FROM detalle_compra dc
            INNER JOIN productos p
                ON p.id = dc.producto_id
            WHERE dc.compra_id = ?
            ORDER BY dc.id
            """,
            (purchase_id,),
        )

        purchase["items"] = [
            dict(item)
            for item in cursor.fetchall()
        ]

        return purchase

    def list_purchases(
        self,
        search: str = "",
    ) -> list[dict]:
        """Lista las compras registradas."""

        cursor = self.database.cursor()

        sql = """
            SELECT
                c.id,
                c.folio,
                c.proveedor_id,
                c.fecha,
                c.subtotal,
                c.total,
                c.notas,
                c.usuario_id
            FROM compras c
            WHERE 1 = 1
        """

        parameters: list = []

        search = search.strip()

        if search:
            sql += """
                AND c.folio LIKE ?
            """

            parameters.append(
                f"%{search}%"
            )

        sql += """
            ORDER BY
                c.fecha DESC,
                c.id DESC
        """

        cursor.execute(
            sql,
            parameters,
        )

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    def _next_folio(
        self,
        fecha: str,
    ) -> str:
        """Genera un folio consecutivo para el día."""

        prefix = f"C-{fecha.replace('-', '')}-"

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT folio
            FROM compras
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
                    int(
                        str(row["folio"]).split("-")[-1]
                    )
                    + 1
                )
            except (ValueError, IndexError):
                sequence = 1

        return f"{prefix}{sequence:04d}"