from app.database.connection import Database


class SupplierService:
    """Administra el catálogo de proveedores."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def list_suppliers(self, search: str = "") -> list[dict]:
        pattern = f"%{search.strip()}%"
        cursor = self.database.cursor()
        cursor.execute(
            """
            SELECT id, nombre, COALESCE(direccion, '') AS direccion,
                   COALESCE(telefono, '') AS telefono, activo
            FROM proveedores
            WHERE activo = 1
              AND (
                  nombre LIKE ? OR COALESCE(direccion, '') LIKE ?
                  OR COALESCE(telefono, '') LIKE ?
              )
            ORDER BY nombre COLLATE NOCASE
            """,
            (pattern, pattern, pattern),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_supplier(self, supplier_id: int) -> dict | None:
        cursor = self.database.cursor()
        cursor.execute(
            """
            SELECT id, nombre, COALESCE(direccion, '') AS direccion,
                   COALESCE(telefono, '') AS telefono, activo
            FROM proveedores WHERE id = ?
            """,
            (supplier_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def save_supplier(
        self,
        name: str,
        address: str = "",
        phone: str = "",
        supplier_id: int | None = None,
    ) -> int:
        name = name.strip()
        if not name:
            raise ValueError("El nombre del proveedor es obligatorio.")

        cursor = self.database.cursor()
        cursor.execute(
            """
            SELECT id FROM proveedores
            WHERE lower(trim(nombre)) = lower(?)
              AND id <> COALESCE(?, -1)
              AND activo = 1
            """,
            (name, supplier_id),
        )
        if cursor.fetchone():
            raise ValueError("Ya existe un proveedor activo con ese nombre.")

        if supplier_id is None:
            cursor.execute(
                """
                INSERT INTO proveedores (nombre, direccion, telefono)
                VALUES (?, ?, ?)
                """,
                (name, address.strip() or None, phone.strip() or None),
            )
            supplier_id = int(cursor.lastrowid)
        else:
            cursor.execute(
                """
                UPDATE proveedores
                SET nombre = ?, direccion = ?, telefono = ?
                WHERE id = ?
                """,
                (
                    name, address.strip() or None, phone.strip() or None,
                    supplier_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError("El proveedor no existe.")
        self.database.commit()
        return int(supplier_id)

    def deactivate_supplier(self, supplier_id: int) -> None:
        cursor = self.database.cursor()
        cursor.execute(
            "UPDATE proveedores SET activo = 0 WHERE id = ?",
            (supplier_id,),
        )
        if cursor.rowcount == 0:
            raise ValueError("El proveedor no existe.")
        self.database.commit()
