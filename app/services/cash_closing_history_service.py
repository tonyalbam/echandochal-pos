"""Consultas históricas de movimientos y cierres de caja chica.

Las cifras de los cierres confirmados son instantáneas inmutables.
Los gastos anulados se conservan en el detalle para trazabilidad y
no se suman entre las salidas efectivas.
"""
from datetime import date

from app.services.petty_cash_service import PettyCashService


class CashClosingHistoryService:
    def __init__(self, database):
        self.database = database
        self.petty_cash = PettyCashService(database)

    def list_years(self):
        cursor = self.database.cursor()
        cursor.execute("""
            SELECT DISTINCT SUBSTR(fecha, 1, 4) AS year
            FROM (
                SELECT fecha FROM cierres_caja
                UNION
                SELECT fecha FROM gastos_caja
            )
            ORDER BY year DESC
        """)
        return [int(row["year"]) for row in cursor.fetchall()]

    def list_history(self, year=None, month=None):
        if month is not None and (month < 1 or month > 12):
            raise ValueError("Mes inválido.")
        if month is not None and year is None:
            raise ValueError("Selecciona un año antes del mes.")
        cursor = self.database.cursor()
        filters, args = [], []
        if year is not None:
            filters.append("SUBSTR(fecha, 1, 4) = ?")
            args.append(f"{int(year):04d}")
        if month is not None:
            filters.append("SUBSTR(fecha, 6, 2) = ?")
            args.append(f"{month:02d}")
        sql = """
            SELECT fecha FROM (
                SELECT fecha FROM cierres_caja
                UNION
                SELECT fecha FROM gastos_caja
            )
        """
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY fecha DESC"
        cursor.execute(sql, args)
        result = []
        for row in cursor.fetchall():
            day = row["fecha"]
            closing = self.petty_cash.get_closing(day)
            if closing:
                record = {
                    "fecha": day, "confirmado": True,
                    "saldo_inicial_centavos": closing["saldo_inicial_centavos"],
                    "ventas_efectivo_centavos": closing["ventas_efectivo_centavos"],
                    "compras_efectivo_centavos": closing["compras_efectivo_centavos"],
                    "gastos_centavos": closing["gastos_centavos"],
                    "saldo_esperado_centavos": closing["saldo_esperado_centavos"],
                    "saldo_contado_centavos": closing["saldo_contado_centavos"],
                    "confirmado_en": closing["confirmado_en"],
                }
            else:
                snapshot = self.petty_cash.get_summary(day)
                record = {
                    "fecha": day, "confirmado": False,
                    "saldo_inicial_centavos": snapshot["saldo_inicial_centavos"],
                    "ventas_efectivo_centavos": snapshot["ventas_efectivo_centavos"],
                    "compras_efectivo_centavos": snapshot["compras_efectivo_centavos"],
                    "gastos_centavos": snapshot["gastos_centavos"],
                    "saldo_esperado_centavos": snapshot["saldo_esperado_centavos"],
                    "saldo_contado_centavos": None, "confirmado_en": None,
                }
            result.append(record)
        return result

    def get_day_detail(self, day):
        day = date.fromisoformat(day).isoformat()
        cursor = self.database.cursor()
        cursor.execute("""
            SELECT id, fecha, tipo, descripcion, monto_centavos,
                   creado_en, anulado, anulado_en
            FROM gastos_caja
            WHERE fecha = ?
            ORDER BY id
        """, (day,))
        expenses = [dict(row) for row in cursor.fetchall()]
        closing = self.petty_cash.get_closing(day)
        if closing:
            opening = closing["saldo_inicial_centavos"]
            sales = closing["ventas_efectivo_centavos"]
            purchases = closing["compras_efectivo_centavos"]
            withdrawals = closing["gastos_centavos"]
            expected = closing["saldo_esperado_centavos"]
        else:
            snapshot = self.petty_cash.get_summary(day)
            opening = snapshot["saldo_inicial_centavos"]
            sales = snapshot["ventas_efectivo_centavos"]
            purchases = snapshot["compras_efectivo_centavos"]
            withdrawals = snapshot["gastos_centavos"]
            expected = snapshot["saldo_esperado_centavos"]
        return {
            "fecha": day, "cierre": closing, "gastos": expenses,
            "saldo_inicial_centavos": opening,
            "ventas_efectivo_centavos": sales,
            "compras_efectivo_centavos": purchases,
            "gastos_centavos": withdrawals,
            "flujos_medios": self.petty_cash.get_payment_flows(day),
            "saldo_esperado_centavos": expected,
            "saldo_contado_centavos": (
                closing["saldo_contado_centavos"] if closing else None
            ),
        }

    @staticmethod
    def summarize(records):
        ordered = sorted(records, key=lambda row: row["fecha"])
        return {
            "dias": len(ordered),
            "confirmados": sum(bool(row["confirmado"]) for row in ordered),
            "ventas_efectivo_centavos": sum(
                row["ventas_efectivo_centavos"] for row in ordered
            ),
            "gastos_centavos": sum(row["gastos_centavos"] for row in ordered),
            "compras_efectivo_centavos": sum(
                row["compras_efectivo_centavos"] for row in ordered
            ),
            # Los saldos inicial/final son posiciones, no flujos sumables.
            "saldo_inicial_centavos": (
                ordered[0]["saldo_inicial_centavos"] if ordered else 0
            ),
            "saldo_final_centavos": (
                ordered[-1]["saldo_contado_centavos"]
                if ordered and ordered[-1]["confirmado"] else None
            ),
        }
