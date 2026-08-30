from datetime import datetime

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

        return {
            "ventas_hoy": self.get_sales_for_period(hoy),
            "ventas_mes": self.get_sales_for_period(mes),
            "ventas_anio": self.get_sales_for_period(anio),
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
        }

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

    def get_monthly_financial_summary(
        self,
        year: int,
    ) -> list[dict]:
        """Devuelve el detalle mensual del reporte financiero anual."""

        report = self.report_service.get_annual_financial_report(
            year
        )

        return report["mensual"]
