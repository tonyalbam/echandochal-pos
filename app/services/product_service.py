from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.database.connection import Database
from app.services.configuration_service import ConfigurationService


class ProductService:
    """Operaciones de negocio relacionadas con productos."""

    INTERNAL_CODE_PREFIX = "ECH"
    INTERNAL_CODE_DIGITS = 7

    ALLOWED_CATEGORIES = (
        "Algodón", "Acrílico", "Combinado", "Clases", "Mercería",
        "Pedidos personalizados", "Talleres", "Patrones",
    )

    def __init__(self, database: Database) -> None:
        self.database = database

    def list_products(
        self,
        search: str = "",
        include_inactive: bool = False,
    ) -> list[dict]:
        cursor = self.database.cursor()

        search = search.strip()
        active_filter = "WHERE p.eliminado = 0" + ("" if include_inactive else " AND p.activo = 1")

        if search:
            pattern = f"%{search}%"
            search_prefix = "AND"

            cursor.execute(
                f"""
                SELECT
                    p.id,
                    p.codigo,
                    p.codigo_barras,
                    p.codigo_qr,
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
                {active_filter}
                  {search_prefix} (
                      p.codigo LIKE ?
                      OR COALESCE(p.codigo_barras, '') LIKE ?
                      OR COALESCE(p.codigo_qr, '') LIKE ?
                      OR p.nombre LIKE ?
                      OR COALESCE(p.marca, '') LIKE ?
                      OR COALESCE(p.color, '') LIKE ?
                  )
                ORDER BY p.activo DESC, p.nombre COLLATE NOCASE
                """,
                (pattern, pattern, pattern, pattern, pattern, pattern),
            )
        else:
            cursor.execute(
                f"""
                SELECT
                    p.id,
                    p.codigo,
                    p.codigo_barras,
                    p.codigo_qr,
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
                {active_filter}
                ORDER BY p.activo DESC, p.nombre COLLATE NOCASE
                """
            )

        return [dict(row) for row in cursor.fetchall()]

    def list_low_stock_products(self, search: str = "") -> list[dict]:
        """Devuelve productos activos agotados o en su mínimo de existencia."""
        products = self.list_products(search)
        low_stock = []
        for product in products:
            existence = float(product["existencia"])
            minimum = float(product["stock_minimo"])
            if existence <= minimum:
                low_stock.append({
                    **product,
                    "faltante_minimo": round(max(minimum - existence, 0), 3),
                })
        return low_stock

    @staticmethod
    def product_status(product: dict) -> str:
        if not product["activo"]:
            return "DESACTIVADO"
        if product["existencia"] <= 0:
            return "AGOTADO"
        if product["existencia"] <= product["stock_minimo"]:
            return "BAJO"
        return "OK"

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

    def get_next_internal_code(self) -> str:
        """Devuelve el siguiente código ECH disponible para un producto nuevo."""

        cursor = self.database.cursor()
        cursor.execute(
            """
            SELECT COALESCE(MAX(CAST(SUBSTR(codigo, 4) AS INTEGER)), 0)
            FROM productos
            WHERE LENGTH(codigo) = 10
              AND codigo LIKE 'ECH%'
              AND SUBSTR(codigo, 4) NOT GLOB '*[^0-9]*'
            """
        )
        sequence = int(cursor.fetchone()[0]) + 1
        maximum = (10 ** self.INTERNAL_CODE_DIGITS) - 1

        while sequence <= maximum:
            code = (
                f"{self.INTERNAL_CODE_PREFIX}"
                f"{sequence:0{self.INTERNAL_CODE_DIGITS}d}"
            )
            cursor.execute(
                """
                SELECT 1
                FROM productos
                WHERE codigo = ?
                   OR codigo_barras = ?
                   OR codigo_qr = ?
                LIMIT 1
                """,
                (code, code, code),
            )
            if cursor.fetchone() is None:
                return code
            sequence += 1

        raise ValueError("Se agotaron los códigos internos disponibles.")

    def create_product(self, data: dict) -> int:
        cursor = self.database.cursor()
        internal_code = self.get_next_internal_code()

        cursor.execute(
            """
            INSERT INTO productos (
                codigo,
                codigo_barras,
                codigo_qr,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                internal_code,
                data.get("codigo_barras") or None,
                data.get("codigo_qr") or None,
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
                codigo_qr = ?,
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
                data.get("codigo_qr") or None,
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

    def delete_product(self, product_id: int) -> None:
        """Oculta un producto sin borrar sus referencias históricas.

        Conservar el ID, código y precios es esencial para tickets, compras,
        ventas, movimientos de inventario y reportes existentes.
        """
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT id, codigo, nombre, eliminado FROM productos WHERE id = ?",
            (int(product_id),),
        )
        product = cursor.fetchone()
        if product is None or product["eliminado"]:
            raise ValueError("El producto no existe o ya fue eliminado.")

        try:
            cursor.execute(
                """UPDATE productos
                   SET eliminado = 1, activo = 0,
                       fecha_actualizacion = CURRENT_TIMESTAMP
                   WHERE id = ? AND eliminado = 0""",
                (int(product_id),),
            )
            cursor.execute(
                """INSERT INTO auditoria
                   (accion, modulo, referencia, detalles)
                   VALUES (?, ?, ?, ?)""",
                (
                    "ELIMINAR_LOGICO", "PRODUCTOS", str(product["codigo"]),
                    f"Producto retirado del catálogo: {product['nombre']}. "
                    "Se conservaron los registros históricos.",
                ),
            )
            self.database.commit()
        except Exception:
            self.database.rollback()
            raise

    def get_categories(self) -> list[dict]:
        cursor = self.database.cursor()
        cursor.execute("""
            SELECT id, nombre FROM categorias WHERE activo = 1
            ORDER BY nombre COLLATE NOCASE
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_units(self) -> list[dict]:
        cursor = self.database.cursor()
        cursor.execute("""
            SELECT id, nombre FROM unidades WHERE activo = 1
            ORDER BY nombre COLLATE NOCASE
        """)
        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def _validate_catalog_name(name: str) -> str:
        name = name.strip()
        if not name or len(name) > 80:
            raise ValueError("Escribe un nombre de 1 a 80 caracteres.")
        return name

    def add_catalog_option(self, kind: str, name: str) -> int:
        """Activa una opción existente o incorpora una nueva."""
        if kind not in ("categorias", "unidades"):
            raise ValueError("Tipo de catálogo desconocido.")
        name = self._validate_catalog_name(name)
        cursor = self.database.cursor()
        cursor.execute(
            f"SELECT id, activo FROM {kind} "
            "WHERE nombre = ? COLLATE NOCASE", (name,)
        )
        existing = cursor.fetchone()
        if existing:
            if existing["activo"]:
                raise ValueError("Esta opción ya existe en el catálogo.")
            cursor.execute(
                f"UPDATE {kind} SET activo = 1 WHERE id = ?",
                (existing["id"],),
            )
            result = int(existing["id"])
        else:
            cursor.execute(
                f"INSERT INTO {kind} (nombre, activo) VALUES (?, 1)",
                (name,),
            )
            result = int(cursor.lastrowid)
        self.database.commit()
        return result

    def remove_catalog_option(self, kind: str, option_id: int) -> None:
        """Deshabilita para futuras altas sin borrar referencias históricas."""
        if kind not in ("categorias", "unidades"):
            raise ValueError("Tipo de catálogo desconocido.")
        cursor = self.database.cursor()
        cursor.execute(
            f"UPDATE {kind} SET activo = 0 WHERE id = ? AND activo = 1",
            (int(option_id),),
        )
        if cursor.rowcount != 1:
            raise ValueError("La opción ya no está disponible.")
        self.database.commit()

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

    def get_inventory_report(self, search: str = "") -> dict:
        """Devuelve el inventario activo y sus indicadores principales."""

        products = self.list_products(search)

        inventory = []
        for product in products:
            stock = float(product["existencia"])
            minimum = float(product["stock_minimo"])
            cost = float(product["costo"])
            price = float(product["precio"])

            if stock <= 0:
                status = "AGOTADO"
            elif stock <= minimum:
                status = "BAJO"
            else:
                status = "OK"

            inventory.append(
                {
                    **product,
                    "faltante_minimo": round(max(minimum - stock, 0), 3),
                    "valor_costo": round(stock * cost, 2),
                    "valor_venta": round(stock * price, 2),
                    "estado_stock": status,
                }
            )

        return {
            "productos": inventory,
            "total_productos": len(inventory),
            "productos_stock_bajo": sum(
                1
                for product in inventory
                if product["estado_stock"] in ("BAJO", "AGOTADO")
            ),
            "valor_total_costo": round(
                sum(product["valor_costo"] for product in inventory),
                2,
            ),
            "valor_total_venta": round(
                sum(product["valor_venta"] for product in inventory),
                2,
            ),
        }

    def export_inventory_report(
        self,
        destination: str | Path,
        search: str = "",
    ) -> Path:
        """Exporta el inventario activo a un archivo Excel."""

        report = self.get_inventory_report(search)
        products = report["productos"]

        output_path = Path(destination)
        if output_path.suffix.lower() != ".xlsx":
            output_path = output_path.with_suffix(".xlsx")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Inventario"

        title_fill = PatternFill("solid", fgColor="1F4E78")
        header_fill = PatternFill("solid", fgColor="D9EAF7")
        warning_fill = PatternFill("solid", fgColor="FFF2CC")
        danger_fill = PatternFill("solid", fgColor="F4CCCC")
        white_bold_font = Font(color="FFFFFF", bold=True)
        bold_font = Font(bold=True)
        money_format = '"$"#,##0.00'

        sheet.merge_cells("A1:O1")
        business_name = ConfigurationService(
            self.database
        ).get_business_name()
        sheet["A1"] = f"{business_name} POS - Reporte de inventario"
        sheet["A1"].fill = title_fill
        sheet["A1"].font = Font(color="FFFFFF", bold=True, size=16)
        sheet["A1"].alignment = Alignment(horizontal="center")

        last_data_row = max(len(products) + 6, 7)
        summary = (
            ("Productos activos", f"=COUNTA(A7:A{last_data_row})"),
            ("Valor a costo", f"=SUM(M7:M{last_data_row})"),
            ("Valor potencial", f"=SUM(N7:N{last_data_row})"),
            (
                "Stock bajo/agotado",
                f'=COUNTIF(O7:O{last_data_row},"BAJO")+'
                f'COUNTIF(O7:O{last_data_row},"AGOTADO")',
            ),
        )
        for index, (label, formula) in enumerate(summary):
            label_column = index * 2 + 1
            value_column = label_column + 1
            label_cell = sheet.cell(row=3, column=label_column, value=label)
            value_cell = sheet.cell(row=3, column=value_column, value=formula)
            label_cell.fill = header_fill
            label_cell.font = bold_font
            value_cell.font = bold_font
            if index in (1, 2):
                value_cell.number_format = money_format

        headers = (
            "Código", "Código de barras", "Producto", "Categoría",
            "Marca", "Proveedor", "Unidad", "Costo", "Precio",
            "Existencia", "Stock mínimo", "Faltante al mínimo",
            "Valor a costo", "Valor potencial", "Estado",
        )
        for column, header in enumerate(headers, start=1):
            cell = sheet.cell(row=6, column=column, value=header)
            cell.fill = title_fill
            cell.font = white_bold_font
            cell.alignment = Alignment(horizontal="center")

        for row, product in enumerate(products, start=7):
            base_values = (
                product["codigo"], product["codigo_barras"] or "",
                product["nombre"], product["categoria"], product["marca"],
                product["proveedor"], product["unidad"], product["costo"],
                product["precio"], product["existencia"],
                product["stock_minimo"],
            )
            for column, value in enumerate(base_values, start=1):
                sheet.cell(row=row, column=column, value=value)

            sheet.cell(row=row, column=12, value=f"=MAX(K{row}-J{row},0)")
            sheet.cell(row=row, column=13, value=f"=H{row}*J{row}")
            sheet.cell(row=row, column=14, value=f"=I{row}*J{row}")
            sheet.cell(
                row=row,
                column=15,
                value=(
                    f'=IF(J{row}<=0,"AGOTADO",'
                    f'IF(J{row}<=K{row},"BAJO","OK"))'
                ),
            )

            for column in (8, 9, 13, 14):
                sheet.cell(row=row, column=column).number_format = money_format
            for column in (10, 11, 12):
                sheet.cell(row=row, column=column).number_format = "#,##0.###"

            status = product["estado_stock"]
            if status == "AGOTADO":
                sheet.cell(row=row, column=15).fill = danger_fill
            elif status == "BAJO":
                sheet.cell(row=row, column=15).fill = warning_fill

        sheet.freeze_panes = "A7"
        if products:
            sheet.auto_filter.ref = f"A6:O{len(products) + 6}"

        widths = (
            16, 20, 34, 20, 18, 24, 12, 14, 14, 14, 15, 19, 16, 17, 13
        )
        for column, width in enumerate(widths, start=1):
            sheet.column_dimensions[get_column_letter(column)].width = width

        workbook.save(output_path)
        return output_path

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
