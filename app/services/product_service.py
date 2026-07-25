from typing import Optional

from app.database.connection import Database


class ProductService:
    """Operaciones de negocio relacionadas con productos."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def list_products(self, search: str = "") -> list[dict]:
        cursor = self.database.cursor()

        search = search.strip()

        if search:
            pattern = f"%{search}%"

            cursor.execute(
                """
                SELECT
                    p.id,
                    p.codigo,
                    p.codigo_barras,
                    p.nombre,
                    COALESCE(c.nombre, '') AS categoria,
                    COALESCE(p.marca, '') AS marca,
                    COALESCE(p.color, '') AS color,
                    p.unidad,
                    p.costo,
                    p.precio,
                    p.existencia,
                    p.stock_minimo,
                    COALESCE(pr.nombre, '') AS proveedor,
                    p.activo
                FROM productos p
                LEFT JOIN categorias c
                    ON c.id = p.categoria_id
                LEFT JOIN proveedores pr
                    ON pr.id = p.proveedor_id
                WHERE p.activo = 1
                  AND (
                      p.codigo LIKE ?
                      OR COALESCE(p.codigo_barras, '') LIKE ?
                      OR p.nombre LIKE ?
                      OR COALESCE(p.marca, '') LIKE ?
                      OR COALESCE(p.color, '') LIKE ?
                  )
                ORDER BY p.nombre COLLATE NOCASE
                """,
                (pattern, pattern, pattern, pattern, pattern),
            )
        else:
            cursor.execute(
                """
                SELECT
                    p.id,
                    p.codigo,
                    p.codigo_barras,
                    p.nombre,
                    COALESCE(c.nombre, '') AS categoria,
                    COALESCE(p.marca, '') AS marca,
                    COALESCE(p.color, '') AS color,
                    p.unidad,
                    p.costo,
                    p.precio,
                    p.existencia,
                    p.stock_minimo,
                    COALESCE(pr.nombre, '') AS proveedor,
                    p.activo
                FROM productos p
                LEFT JOIN categorias c
                    ON c.id = p.categoria_id
                LEFT JOIN proveedores pr
                    ON pr.id = p.proveedor_id
                WHERE p.activo = 1
                ORDER BY p.nombre COLLATE NOCASE
                """
            )

        return [dict(row) for row in cursor.fetchall()]

    def get_product(self, product_id: int) -> Optional[dict]:
        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT
                p.*,
                COALESCE(c.nombre, '') AS categoria_nombre,
                COALESCE(pr.nombre, '') AS proveedor_nombre
            FROM productos p
            LEFT JOIN categorias c
                ON c.id = p.categoria_id
            LEFT JOIN proveedores pr
                ON pr.id = p.proveedor_id
            WHERE p.id = ?
            """,
            (product_id,),
        )

        row = cursor.fetchone()

        return dict(row) if row else None

    def create_product(self, data: dict) -> int:
        cursor = self.database.cursor()

        cursor.execute(
            """
            INSERT INTO productos (
                codigo,
                codigo_barras,
                nombre,
                categoria_id,
                marca,
                color,
                unidad,
                costo,
                precio,
                existencia,
                stock_minimo,
                proveedor_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["codigo"],
                data.get("codigo_barras") or None,
                data["nombre"],
                data.get("categoria_id"),
                data.get("marca") or None,
                data.get("color") or None,
                data.get("unidad") or "pieza",
                data.get("costo", 0),
                data.get("precio", 0),
                data.get("existencia", 0),
                data.get("stock_minimo", 0),
                data.get("proveedor_id"),
            ),
        )

        product_id = cursor.lastrowid

        self.database.commit()

        return int(product_id)

    def update_product(self, product_id: int, data: dict) -> None:
        cursor = self.database.cursor()

        cursor.execute(
            """
            UPDATE productos
            SET
                codigo = ?,
                codigo_barras = ?,
                nombre = ?,
                categoria_id = ?,
                marca = ?,
                color = ?,
                unidad = ?,
                costo = ?,
                precio = ?,
                existencia = ?,
                stock_minimo = ?,
                proveedor_id = ?,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                data["codigo"],
                data.get("codigo_barras") or None,
                data["nombre"],
                data.get("categoria_id"),
                data.get("marca") or None,
                data.get("color") or None,
                data.get("unidad") or "pieza",
                data.get("costo", 0),
                data.get("precio", 0),
                data.get("existencia", 0),
                data.get("stock_minimo", 0),
                data.get("proveedor_id"),
                product_id,
            ),
        )

        self.database.commit()

    def deactivate_product(self, product_id: int) -> None:
        cursor = self.database.cursor()

        cursor.execute(
            """
            UPDATE productos
            SET
                activo = 0,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (product_id,),
        )

        self.database.commit()

    def get_categories(self) -> list[dict]:
        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT id, nombre
            FROM categorias
            WHERE activo = 1
            ORDER BY nombre COLLATE NOCASE
            """
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_suppliers(self) -> list[dict]:
        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT id, nombre
            FROM proveedores
            WHERE activo = 1
            ORDER BY nombre COLLATE NOCASE
            """
        )

        return [dict(row) for row in cursor.fetchall()]

    def create_category(self, name: str) -> int:
        cursor = self.database.cursor()

        cursor.execute(
            """
            INSERT INTO categorias (nombre)
            VALUES (?)
            """,
            (name.strip(),),
        )

        category_id = cursor.lastrowid

        self.database.commit()

        return int(category_id)

    def create_supplier(self, name: str) -> int:
        cursor = self.database.cursor()

        cursor.execute(
            """
            INSERT INTO proveedores (nombre)
            VALUES (?)
            """,
            (name.strip(),),
        )

        supplier_id = cursor.lastrowid

        self.database.commit()

        return int(supplier_id)
