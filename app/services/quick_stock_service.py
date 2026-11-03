"""Recepción rápida por escáner, con confirmación explícita y transacción única."""

from app.database.connection import Database


class QuickStockService:
    """Acumula lecturas sin escribir en la BD hasta guardar."""

    MAX_QUANTITY = 1000000

    def __init__(self, database: Database):
        self.database = database
        self.pending: dict[int, int] = {}
        self.products: dict[int, dict] = {}

    def find_scanned_product(self, code: str) -> dict:
        code = code.strip()
        if not code:
            raise ValueError("Escanea un código válido.")
        cursor = self.database.cursor()
        cursor.execute(
            """SELECT id, codigo, codigo_barras, codigo_qr, nombre, marca,
                      color, existencia, activo, eliminado
                 FROM productos
                WHERE activo = 1 AND eliminado = 0
                  AND (codigo = ? OR codigo_barras = ? OR codigo_qr = ?)""",
            (code, code, code),
        )
        matches = [dict(row) for row in cursor.fetchall()]
        if not matches:
            raise ValueError(
                f"No existe un producto activo con el código '{code}'. "
                "El inventario no se modificó."
            )
        if len(matches) != 1:
            raise ValueError(
                "Este código coincide con varios productos. "
                "Corrige los códigos duplicados antes de continuar."
            )
        return matches[0]

    def add_scan(self, code: str) -> dict:
        product = self.find_scanned_product(code)
        product_id = int(product["id"])
        self.set_quantity(product_id, self.pending.get(product_id, 0) + 1,
                          product=product)
        return product

    def set_quantity(self, product_id: int, quantity: int,
                     product: dict | None = None) -> None:
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError("La cantidad debe ser un número entero.")
        if quantity < 0 or quantity > self.MAX_QUANTITY:
            raise ValueError("La cantidad está fuera del rango permitido.")
        if quantity == 0:
            self.pending.pop(product_id, None)
            self.products.pop(product_id, None)
            return
        if product_id not in self.products:
            if product is None:
                cursor = self.database.cursor()
                cursor.execute(
                    """SELECT id, codigo, nombre, marca, color, existencia,
                              activo, eliminado
                         FROM productos WHERE id = ?""", (product_id,)
                )
                row = cursor.fetchone()
                product = dict(row) if row else None
            if product is None or not product["activo"] or product["eliminado"]:
                raise ValueError("El producto no está disponible para recepción.")
            self.products[product_id] = product
        self.pending[product_id] = quantity

    def save(self) -> int:
        if not self.pending:
            raise ValueError("No hay productos pendientes de guardar.")
        cursor = self.database.cursor()
        try:
            cursor.execute("BEGIN")
            for product_id, quantity in self.pending.items():
                if quantity <= 0 or quantity > self.MAX_QUANTITY:
                    raise ValueError("Cantidad de recepción inválida.")
                cursor.execute(
                    """SELECT existencia, activo, eliminado
                         FROM productos WHERE id = ?""", (product_id,)
                )
                row = cursor.fetchone()
                if row is None or not row["activo"] or row["eliminado"]:
                    raise ValueError(
                        "Uno de los productos fue desactivado o eliminado. "
                        "No se guardaron los cambios."
                    )
                previous = float(row["existencia"])
                new_stock = previous + quantity
                cursor.execute(
                    """UPDATE productos
                          SET existencia = ?, fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE id = ? AND activo = 1 AND eliminado = 0""",
                    (new_stock, product_id),
                )
                cursor.execute(
                    """INSERT INTO movimientos_inventario
                       (producto_id, tipo, cantidad, existencia_anterior,
                        existencia_nueva, referencia)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (product_id, "ENTRADA_RAPIDA", quantity, previous,
                     new_stock, "Recepción rápida por escáner"),
                )
            self.database.commit()
        except Exception:
            self.database.rollback()
            raise
        saved = sum(self.pending.values())
        self.pending.clear()
        self.products.clear()
        return saved
