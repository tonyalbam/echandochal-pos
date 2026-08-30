from app.database.connection import Database


class ReportService:
    """Consultas y cálculos para reportes financieros."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def get_annual_financial_report(
        self,
        year: int,
    ) -> dict:
        """
        Devuelve el resumen financiero anual y
        el detalle mensual del año indicado.
        """

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT
                substr(v.fecha, 6, 2) AS mes,
                COALESCE(SUM(v.total), 0) AS ventas,
                COALESCE(SUM(v.monto_comision), 0) AS comisiones,
                COALESCE(SUM(costos.costo), 0) AS costo
            FROM ventas v
            LEFT JOIN (
                SELECT
                    venta_id,
                    SUM(
                        cantidad * costo_unitario
                    ) AS costo
                FROM detalle_venta
                GROUP BY venta_id
            ) costos
                ON costos.venta_id = v.id
            WHERE v.cancelada = 0
              AND substr(v.fecha, 1, 4) = ?
            GROUP BY substr(v.fecha, 6, 2)
            ORDER BY mes
            """,
            (str(year),),
        )

        rows = cursor.fetchall()

        data_by_month = {
            int(row["mes"]): {
                "ventas": float(row["ventas"]),
                "comisiones": float(
                    row["comisiones"]
                ),
                "costo": float(row["costo"]),
            }
            for row in rows
        }

        monthly = []

        total_sales = 0.0
        total_commissions = 0.0
        total_cost = 0.0

        for month in range(1, 13):
            values = data_by_month.get(
                month,
                {
                    "ventas": 0.0,
                    "comisiones": 0.0,
                    "costo": 0.0,
                },
            )

            sales = values["ventas"]
            commissions = values["comisiones"]
            cost = values["costo"]

            net_income = sales - commissions
            profit = sales - cost - commissions

            monthly.append(
                {
                    "mes": month,
                    "ventas": round(sales, 2),
                    "comisiones": round(
                        commissions,
                        2,
                    ),
                    "costo": round(cost, 2),
                    "ingreso_neto": round(
                        net_income,
                        2,
                    ),
                    "utilidad": round(
                        profit,
                        2,
                    ),
                }
            )

            total_sales += sales
            total_commissions += commissions
            total_cost += cost

        total_net_income = (
            total_sales - total_commissions
        )

        total_profit = (
            total_sales
            - total_cost
            - total_commissions
        )

        return {
            "year": year,
            "ventas": round(total_sales, 2),
            "costo": round(total_cost, 2),
            "comisiones": round(
                total_commissions,
                2,
            ),
            "ingreso_neto": round(
                total_net_income,
                2,
            ),
            "utilidad": round(
                total_profit,
                2,
            ),
            "mensual": monthly,
        }