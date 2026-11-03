from datetime import date, datetime
from pathlib import Path

from app.database.connection import Database
from app.services.report_service import ReportService


class DashboardService:
    """Obtiene estadísticas financieras y operativas del negocio."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.report_service = ReportService(database)

    def get_summary(self) -> dict:
        """Devuelve los principales indicadores del Dashboard."""

        hoy = datetime.now().strftime("%Y-%m-%d")
        mes = hoy[:7]
        anio = hoy[:4]

        top_products_month = self.get_top_selling_products_for_period(mes)
        top_products_year = self.get_top_selling_products_for_period(anio)
        top_product = top_products_month[0] if top_products_month else None
        payment_sales = self.get_payment_sales_for_period(mes)

        return {
            "ventas_hoy": self.get_sales_for_period(hoy),
            "ventas_mes": self.get_sales_for_period(mes),
            "ventas_anio": self.get_sales_for_period(anio),
            "ventas_efectivo_mes": payment_sales["Efectivo"],
            "ventas_transferencia_mes": payment_sales["Transferencia"],
            "ventas_mercado_libre_mes": payment_sales["Mercado Libre"],
            "utilidad_hoy": self.get_profit_for_period(hoy),
            "utilidad_mes": self.get_profit_for_period(mes),
            "utilidad_anio": self.get_profit_for_period(anio),
            "comisiones_hoy": self.get_commissions_for_period(hoy),
            "comisiones_mes": self.get_commissions_for_period(mes),
            "comisiones_anio": self.get_commissions_for_period(anio),
            "ingreso_neto_hoy": self.get_net_income_for_period(hoy),
            "ingreso_neto_mes": self.get_net_income_for_period(mes),
            "ingreso_neto_anio": self.get_net_income_for_period(anio),
            "ticket_promedio": self.get_average_ticket_for_period(mes),
            "numero_ventas": self.get_sales_count_for_period(mes),
            "valor_inventario": self.get_inventory_value(),
            "stock_bajo": self.get_low_stock_count(),
            "margen_utilidad_mes": self.get_profit_margin_for_period(mes),
            "unidades_vendidas_mes": self.get_units_sold_for_period(mes),
            "producto_mas_vendido": (
                top_product["nombre"] if top_product else "Sin ventas"
            ),
            "producto_mas_vendido_unidades": (
                top_product["cantidad"] if top_product else 0.0
            ),
            "productos_mas_vendidos_mes": top_products_month,
            "productos_mas_vendidos_anio": top_products_year,
        }

    def get_payment_sales_for_period(self, period: str) -> dict[str, float]:
        """Obtiene ventas por forma de pago registrada en cada partida."""

        cursor = self.database.cursor()
        cursor.execute(
            """
            SELECT p.metodo_pago, ROUND(SUM(p.ventas), 2) AS ventas
            FROM resumen_pagos_venta p
            JOIN ventas v ON v.id = p.venta_id
            WHERE v.cancelada = 0 AND v.fecha LIKE ?
            GROUP BY p.metodo_pago
            """,
            (f"{period}%",),
        )
        result = {method: 0.0 for method in self.report_service.PAYMENT_METHODS}
        for row in cursor.fetchall():
            if row["metodo_pago"] in result:
                result[row["metodo_pago"]] = round(float(row["ventas"]), 2)
        return result

    def get_sales_for_period(self, period: str) -> float:
        """Obtiene ventas no canceladas de un periodo."""

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT COALESCE(SUM(total), 0)
            FROM ventas
            WHERE cancelada = 0
              AND fecha LIKE ?
            """,
            (f"{period}%",),
        )

        return round(float(cursor.fetchone()[0]), 2)
    
    def get_profit_for_period(self, period: str) -> float:
        """Obtiene utilidad después de costo y comisiones."""

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT
                COALESCE(SUM(v.total), 0) AS ventas,
                COALESCE(SUM(v.monto_comision), 0) AS comisiones,
                COALESCE(SUM(costos.costo), 0) AS costo
            FROM ventas v
            LEFT JOIN (
                SELECT
                    venta_id,
                    SUM(cantidad * costo_unitario) AS costo
                FROM detalle_venta
                GROUP BY venta_id
            ) costos
                ON costos.venta_id = v.id
            WHERE v.cancelada = 0
              AND v.fecha LIKE ?
            """,
            (f"{period}%",),
        )

        row = cursor.fetchone()

        ventas = float(row["ventas"])
        comisiones = float(row["comisiones"])
        costo = float(row["costo"])

        return round(
            ventas - costo - comisiones,
            2,
        )
        
    def get_commissions_for_period(
        self,
        period: str,
    ) -> float:
        """Obtiene las comisiones cobradas en un periodo."""

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT COALESCE(SUM(monto_comision), 0)
            FROM ventas
            WHERE cancelada = 0
              AND fecha LIKE ?
            """,
            (f"{period}%",),
        )

        return round(float(cursor.fetchone()[0]), 2)

    def get_net_income_for_period(
        self,
        period: str,
    ) -> float:
        """Obtiene ventas menos comisiones."""

        ventas = self.get_sales_for_period(period)
        comisiones = self.get_commissions_for_period(period)

        return round(
            ventas - comisiones,
            2,
        )

    def get_average_ticket_for_period(
        self,
        period: str,
    ) -> float:
        """Obtiene el ticket promedio."""

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT
                COALESCE(AVG(total), 0)
            FROM ventas
            WHERE cancelada = 0
              AND fecha LIKE ?
            """,
            (f"{period}%",),
        )

        return round(float(cursor.fetchone()[0]), 2)

    def get_sales_count_for_period(
        self,
        period: str,
    ) -> int:
        """Obtiene la cantidad de ventas de un periodo."""

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM ventas
            WHERE cancelada = 0
              AND fecha LIKE ?
            """,
            (f"{period}%",),
        )

        return int(cursor.fetchone()[0])

    def get_inventory_value(self) -> float:
        """Obtiene el valor del inventario a costo."""

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT COALESCE(
                SUM(existencia * costo),
                0
            )
            FROM productos
            WHERE activo = 1
            """
        )

        return round(float(cursor.fetchone()[0]), 2)

    def get_low_stock_count(self) -> int:
        """Cuenta productos agotados o por debajo del stock mínimo."""

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM productos
            WHERE activo = 1
              AND existencia <= stock_minimo
            """
        )

        return int(cursor.fetchone()[0])

    def get_profit_margin_for_period(self, period: str) -> float:
        """Obtiene el porcentaje de utilidad sobre las ventas."""

        sales = self.get_sales_for_period(period)
        if sales <= 0:
            return 0.0

        profit = self.get_profit_for_period(period)
        return round((profit / sales) * 100, 2)

    def get_units_sold_for_period(self, period: str) -> float:
        """Obtiene las unidades incluidas en ventas no canceladas."""

        cursor = self.database.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(dv.cantidad), 0)
            FROM detalle_venta dv
            INNER JOIN ventas v
                ON v.id = dv.venta_id
            WHERE v.cancelada = 0
              AND v.fecha LIKE ?
            """,
            (f"{period}%",),
        )

        return round(float(cursor.fetchone()[0]), 2)

    def get_top_selling_product_for_period(
        self,
        period: str,
    ) -> dict | None:
        """Obtiene el producto con más unidades vendidas."""

        products = self.get_top_selling_products_for_period(period, limit=1)
        return products[0] if products else None

    def get_top_selling_products_for_period(
        self,
        period: str,
        limit: int = 5,
    ) -> list[dict]:
        """Obtiene hasta cinco productos ordenados por unidades vendidas."""

        limit = max(1, min(int(limit), 100))
        cursor = self.database.cursor()
        cursor.execute(
            """
            SELECT
                p.id,
                p.codigo,
                p.nombre,
                SUM(dv.cantidad) AS cantidad,
                SUM(dv.subtotal) AS importe
            FROM detalle_venta dv
            INNER JOIN ventas v
                ON v.id = dv.venta_id
            INNER JOIN productos p
                ON p.id = dv.producto_id
            WHERE v.cancelada = 0
              AND v.fecha LIKE ?
            GROUP BY p.id, p.codigo, p.nombre
            ORDER BY
                cantidad DESC,
                importe DESC,
                p.nombre
            LIMIT ?
            """,
            (f"{period}%", limit),
        )

        return [
            {
                "id": int(row["id"]),
                "codigo": row["codigo"],
                "nombre": row["nombre"],
                "cantidad": round(float(row["cantidad"]), 2),
                "importe": round(float(row["importe"]), 2),
            }
            for row in cursor.fetchall()
        ]

    def get_monthly_financial_summary(
        self,
        year: int,
    ) -> list[dict]:
        """Devuelve el detalle mensual del reporte financiero anual."""

        report = self.report_service.get_annual_financial_report(
            year
        )

        return report["mensual"]

    def get_analytics_annual(self, year: int, today: date | None = None) -> dict:
        """Indicadores visuales del año sin modificar datos.

        Los importes y comisiones de la venta se prorratean por subtotal
        entre partidas, evitando duplicar importes de cobros mixtos.
        """
        today = today or date.today()
        if year < 2000 or year > 9999:
            raise ValueError("Año inválido.")
        cursor = self.database.cursor()
        cursor.execute(
            """SELECT v.id AS venta_id, v.fecha, v.total,
                      v.monto_comision, dv.producto_id, dv.cantidad,
                      dv.subtotal, dv.costo_unitario,
                      p.nombre, p.codigo,
                      COALESCE(NULLIF(TRIM(p.marca), ''), 'Sin marca') AS marca,
                      COALESCE(c.nombre, 'Sin categoría') AS categoria
               FROM detalle_venta dv
               JOIN ventas v ON v.id = dv.venta_id
               JOIN productos p ON p.id = dv.producto_id
               LEFT JOIN categorias c ON c.id = p.categoria_id
               WHERE v.cancelada = 0 AND v.fecha LIKE ?
               ORDER BY v.id, dv.id""",
            (f"{year}-%",),
        )
        lines = [dict(row) for row in cursor.fetchall()]
        sale_subtotals = {}
        for line in lines:
            sid = line["venta_id"]
            sale_subtotals[sid] = sale_subtotals.get(sid, 0) + float(line["subtotal"])

        brands = {}
        products = {}
        for line in lines:
            quantity = float(line["cantidad"])
            product_id = int(line["producto_id"])
            gross_total = sale_subtotals[line["venta_id"]]
            ratio = float(line["subtotal"]) / gross_total if gross_total else 0.0
            sales = float(line["total"]) * ratio
            commission = float(line["monto_comision"]) * ratio
            profit = sales - commission - quantity * float(line["costo_unitario"])
            brands[line["marca"]] = brands.get(line["marca"], 0.0) + quantity
            if product_id not in products:
                products[product_id] = {
                    "id": product_id, "codigo": line["codigo"],
                    "nombre": line["nombre"], "categoria": line["categoria"],
                    "unidades": 0.0, "ventas": 0.0, "utilidad": 0.0,
                }
            entry = products[product_id]
            entry["unidades"] += quantity
            entry["ventas"] += sales
            entry["utilidad"] += profit

        best_brand = None
        if brands:
            name, units = sorted(
                brands.items(), key=lambda pair: (-pair[1], pair[0].casefold())
            )[0]
            best_brand = {"nombre": name, "unidades": round(units, 2)}

        best_units = sorted(
            products.values(),
            key=lambda item: (-item["unidades"], -item["ventas"], item["nombre"]),
        )
        best_profit = sorted(
            products.values(),
            key=lambda item: (-item["utilidad"], item["nombre"]),
        )
        top_revenue = sorted(
            products.values(),
            key=lambda item: (-item["ventas"], item["nombre"]),
        )[:5]
        total_top_revenue = sum(row["ventas"] for row in top_revenue)
        for item in top_revenue:
            item["porcentaje"] = round(
                100 * item["ventas"] / total_top_revenue, 1
            ) if total_top_revenue > 0 else 0.0

        cursor.execute(
            """SELECT p.id, p.codigo, p.nombre, p.existencia, p.costo,
                      p.precio, p.fecha_creacion,
                      COALESCE(NULLIF(TRIM(p.marca), ''), 'Sin marca') AS marca,
                      COALESCE(c.nombre, 'Sin categoría') AS categoria,
                      MAX(CASE WHEN v.cancelada = 0 THEN v.fecha END) AS ultima_venta
               FROM productos p
               LEFT JOIN categorias c ON c.id = p.categoria_id
               LEFT JOIN detalle_venta dv ON dv.producto_id = p.id
               LEFT JOIN ventas v ON v.id = dv.venta_id
               WHERE p.activo = 1 AND p.eliminado = 0 AND p.existencia > 0
               GROUP BY p.id""",
        )
        aged = []
        for row in cursor.fetchall():
            created = date.fromisoformat(row["fecha_creacion"][:10])
            last_sold = date.fromisoformat(row["ultima_venta"]) if row["ultima_venta"] else None
            reference = last_sold or created
            days = (today - reference).days
            if days <= 90:
                continue
            aged.append({
                "id": int(row["id"]), "codigo": row["codigo"],
                "nombre": row["nombre"], "marca": row["marca"],
                "categoria": row["categoria"], "existencia": float(row["existencia"]),
                "costo": float(row["costo"]), "precio": float(row["precio"]),
                "ultima_venta": row["ultima_venta"],
                "dias_sin_venta": days,
                "dias_en_inventario": (today - created).days,
                "valor_inmovilizado": round(
                    float(row["existencia"]) * float(row["costo"]), 2
                ),
            })
        aged.sort(key=lambda row: (-row["dias_sin_venta"], row["nombre"]))
        # Menor rotación: priorizar cero ventas anuales y después antigüedad.
        cursor.execute(
            """SELECT p.id, p.nombre, p.fecha_creacion,
                      COALESCE(SUM(CASE WHEN v.cancelada = 0
                          AND v.fecha LIKE ? THEN dv.cantidad ELSE 0 END), 0)
                          AS unidades_anuales
               FROM productos p
               LEFT JOIN detalle_venta dv ON dv.producto_id = p.id
               LEFT JOIN ventas v ON v.id = dv.venta_id
               WHERE p.activo = 1 AND p.eliminado = 0 AND p.existencia > 0
               GROUP BY p.id""",
            (f"{year}-%",),
        )
        inventory = [
            {
                "id": int(row["id"]), "nombre": row["nombre"],
                "unidades": float(row["unidades_anuales"]),
                "dias": (today - date.fromisoformat(row["fecha_creacion"][:10])).days,
            }
            for row in cursor.fetchall()
        ]
        # Menor rotación: solo productos con 90 días o más desde su alta.
        # Entre los elegibles, gana el de menos unidades vendidas en el año;
        # los empates se resuelven por mayor antigüedad.
        eligible_inventory = [
            product for product in inventory if product["dias"] >= 90
        ]
        slowest = (
            sorted(
                eligible_inventory,
                key=lambda row: (row["unidades"], -row["dias"], row["nombre"]),
            )[0] if eligible_inventory else None
        )

        accumulated = 0.0
        months = []
        for month in range(1, 13):
            # Para el año en curso no proyectar utilidad hacia meses futuros.
            # Mantener las doce etiquetas en el eje X sin trazar esos puntos.
            if year > today.year or (year == today.year and month > today.month):
                months.append({
                    "mes": month, "utilidad": None, "acumulada": None
                })
                continue
            monthly = self.get_profit_for_period(f"{year}-{month:02d}")
            accumulated = round(accumulated + monthly, 2)
            months.append({
                "mes": month, "utilidad": monthly,
                "acumulada": accumulated
            })

        return {
            "year": year,
            "marca_mas_vendida": best_brand,
            "producto_mas_vendido": best_units[0] if best_units else None,
            "producto_mas_rentable": best_profit[0] if best_profit else None,
            "producto_menos_vendido": slowest,
            "utilidad_acumulada": months,
            "top_productos_ingresos": top_revenue,
            "sin_venta_90_dias": aged,
        }

    def export_annual_financial_report(
        self,
        year: int,
        destination: str | Path,
    ) -> Path:
        """Exporta el reporte anual utilizado por el Dashboard."""

        return self.report_service.export_annual_financial_report(
            year,
            destination,
        )
