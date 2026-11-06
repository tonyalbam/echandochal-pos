"""Corte general: acumulados y conciliación de efectivo, tarjeta y transferencia.

El arqueo físico de caja chica se confirma por separado y es la fuente de
verdad del efectivo. Los saldos bancarios sólo se conocen cuando el usuario
registra el saldo inicial y el saldo real; nunca se infieren de los flujos.
"""
from datetime import date

from app.services.payment_allocation import cents
from app.services.petty_cash_service import PettyCashService


class GeneralClosingService:
    METHODS = ("Efectivo", "Tarjeta", "Transferencia")
    CONCEPTS = (
        ("venta_efectivo", "Ventas netas en efectivo", "Entrada"),
        ("venta_tarjeta", "Ventas netas en tarjeta (comisión descontada)", "Entrada"),
        ("venta_transferencia", "Ventas por transferencia", "Entrada"),
        ("compra_efectivo", "Compras pagadas en efectivo", "Salida"),
        ("compra_tarjeta", "Compras pagadas con tarjeta", "Salida"),
        ("compra_transferencia", "Compras pagadas por transferencia", "Salida"),
        ("gasto_fijo", "Gastos Fijos de caja chica", "Salida"),
        ("gasto_variable", "Gastos variables de caja chica", "Salida"),
        ("sobre_valores", "Sobre/Valores (traspaso de efectivo)", "Salida"),
    )

    def __init__(self, database):
        self.database = database
        self.petty_cash = PettyCashService(database)

    @staticmethod
    def _day(value):
        return date.fromisoformat(value).isoformat()

    def get_closing(self, day):
        day = self._day(day)
        cursor = self.database.cursor()
        cursor.execute("SELECT * FROM cortes_generales WHERE fecha = ?", (day,))
        row = cursor.fetchone()
        if not row:
            return None
        closing = dict(row)
        cursor.execute(
            """SELECT * FROM detalle_corte_general
               WHERE fecha = ?""", (day,)
        )
        closing["medios"] = {
            item["metodo_pago"]: dict(item) for item in cursor.fetchall()
        }
        return closing

    def _previous_closing(self, day):
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT fecha FROM cortes_generales WHERE fecha < ? "
            "ORDER BY fecha DESC LIMIT 1", (day,)
        )
        item = cursor.fetchone()
        return self.get_closing(item["fecha"]) if item else None

    def get_summary(self, day, initial_card=None, initial_transfer=None):
        day = self._day(day)
        petty = self.petty_cash.get_summary(day)
        flows = {
            item["metodo_pago"]: item
            for item in self.petty_cash.get_payment_flows(day)
        }
        expense_cash = petty["gastos_centavos"]
        previous = self._previous_closing(day)
        saved = self.get_closing(day)
        manual = {"Tarjeta": initial_card, "Transferencia": initial_transfer}
        rows = []
        for method in self.METHODS:
            flow = flows[method]
            if method == "Efectivo":
                opening = petty["saldo_inicial_centavos"]
            elif previous:
                opening = previous["medios"][method]["saldo_real_centavos"]
            elif manual[method] is not None:
                opening = cents(manual[method])
            else:
                opening = None

            sales = flow["entradas_centavos"]
            purchases = flow["compras_centavos"]
            other = expense_cash if method == "Efectivo" else 0
            expected = (
                opening + sales - purchases - other
                if opening is not None else None
            )
            actual = None
            difference = None
            if saved:
                snapshot = saved["medios"][method]
                # Presentar siempre los importes del cierre histórico, sin
                # recalcularlo a partir de movimientos posteriores.
                opening = snapshot["saldo_inicial_centavos"]
                sales = snapshot["entradas_centavos"]
                purchases = snapshot["compras_centavos"]
                other = snapshot["otras_salidas_centavos"]
                expected = snapshot["saldo_esperado_centavos"]
                actual = snapshot["saldo_real_centavos"]
                difference = snapshot["diferencia_centavos"]
            rows.append({
                "metodo_pago": method,
                "saldo_inicial_centavos": opening,
                "entradas_centavos": sales,
                "compras_centavos": purchases,
                "otras_salidas_centavos": other,
                "saldo_esperado_centavos": expected,
                "saldo_real_centavos": actual,
                "diferencia_centavos": difference,
            })
        return {
            "fecha": day, "cierre": saved,
            "cierre_caja_chica": petty["cierre"],
            "cierre_anterior": previous["fecha"] if previous else None,
            "medios": rows,
        }

    def get_concept_movements(self, day):
        """Flujos de hoy y acumulados por concepto hasta la fecha indicada.

        Nunca suma saldos bancarios de días distintos; acumula MOVIMIENTOS.
        """
        day = self._day(day)
        cursor = self.database.cursor()
        amounts = {key: [0, 0] for key, _, _ in self.CONCEPTS}
        methods = {"Efectivo": "efectivo",
                   "Mercado Libre": "tarjeta",
                   "Transferencia": "transferencia"}
        for index, condition in enumerate(("= ?", "<= ?")):
            cursor.execute(
                f"""SELECT p.metodo_pago,
                           ROUND(COALESCE(SUM(p.ventas - p.comisiones), 0), 2)
                    FROM resumen_pagos_venta p
                    JOIN ventas v ON v.id = p.venta_id
                    WHERE v.fecha {condition} AND v.cancelada = 0
                    GROUP BY p.metodo_pago""",
                (day,),
            )
            for method, value in cursor.fetchall():
                suffix = methods.get(method)
                if suffix is not None:
                    amounts["venta_" + suffix][index] = cents(value)
            cursor.execute(
                f"""SELECT pc.metodo_pago, COALESCE(SUM(pc.monto_centavos), 0)
                    FROM pagos_compra pc
                    JOIN compras c ON c.id = pc.compra_id
                    WHERE c.fecha {condition}
                    GROUP BY pc.metodo_pago""",
                (day,),
            )
            for method, value in cursor.fetchall():
                suffix = method.lower()
                if suffix in ("efectivo", "tarjeta", "transferencia"):
                    amounts["compra_" + suffix][index] = int(value)
            cursor.execute(
                f"""SELECT tipo, COALESCE(SUM(monto_centavos), 0)
                    FROM gastos_caja
                    WHERE fecha {condition} AND anulado = 0
                    GROUP BY tipo""",
                (day,),
            )
            mapping = {
                "Gastos Fijos": "gasto_fijo",
                "Gastos variables": "gasto_variable",
                "Sobre/Valores": "sobre_valores",
            }
            for kind, value in cursor.fetchall():
                if kind in mapping:
                    amounts[mapping[kind]][index] = int(value)
        return [
            {
                "clave": key, "concepto": label, "tipo": kind,
                "dia_centavos": amounts[key][0],
                "acumulado_centavos": amounts[key][1],
            }
            for key, label, kind in self.CONCEPTS
        ]

    def _assert_no_unclosed_intervening_operations(self, day, previous):
        """No arrastrar bancos desde un corte saltando movimientos conocidos."""
        if not previous:
            return
        start = previous["fecha"]
        cursor = self.database.cursor()
        queries = (
            """SELECT MIN(fecha) FROM ventas
               WHERE fecha > ? AND fecha < ? AND cancelada = 0""",
            """SELECT MIN(fecha) FROM compras
               WHERE fecha > ? AND fecha < ?""",
            """SELECT MIN(fecha) FROM gastos_caja
               WHERE fecha > ? AND fecha < ? AND anulado = 0""",
        )
        for sql in queries:
            cursor.execute(sql, (start, day))
            pending = cursor.fetchone()[0]
            if pending:
                raise ValueError(
                    "Existen movimientos del día " + pending +
                    " sin corte general confirmado. Confirma primero ese día."
                )

    def confirm(self, day, real_balances, initial_balances, notes=""):
        day = self._day(day)
        if day > date.today().isoformat():
            raise ValueError("No se puede confirmar un corte general futuro.")
        if self.get_closing(day):
            raise ValueError("El corte general de esta fecha ya está confirmado.")
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT fecha FROM cortes_generales WHERE fecha > ? LIMIT 1", (day,)
        )
        if cursor.fetchone():
            raise ValueError("Ya existe un corte general posterior confirmado.")

        petty_closing = self.petty_cash.get_closing(day)
        if not petty_closing:
            raise ValueError(
                "Primero confirma el corte de efectivo en Caja chica."
            )
        if set(real_balances) != set(self.METHODS):
            raise ValueError("Captura el saldo real de los tres medios de pago.")
        if not isinstance(initial_balances, dict):
            raise ValueError("Debes indicar los saldos iniciales.")
        if len(notes) > 500:
            raise ValueError("Las observaciones no pueden superar 500 caracteres.")

        previous = self._previous_closing(day)
        self._assert_no_unclosed_intervening_operations(day, previous)
        initial_card = (
            None if previous else initial_balances.get("Tarjeta")
        )
        initial_transfer = (
            None if previous else initial_balances.get("Transferencia")
        )
        if not previous and (initial_card is None or initial_transfer is None):
            raise ValueError(
                "Captura los saldos iniciales de tarjeta y transferencia "
                "antes del primer corte general."
            )
        data = self.get_summary(day, initial_card, initial_transfer)
        rows = []
        for row in data["medios"]:
            method = row["metodo_pago"]
            opening = row["saldo_inicial_centavos"]
            expected = row["saldo_esperado_centavos"]
            actual = cents(real_balances[method])
            if opening is None or opening < 0 or actual < 0:
                raise ValueError("Los saldos no pueden ser negativos o estar vacíos.")
            if expected < 0:
                raise ValueError(
                    f"El saldo esperado en {method} es negativo. "
                    "Revisa el saldo inicial y las salidas."
                )
            if (method == "Efectivo" and
                    actual != petty_closing["saldo_contado_centavos"]):
                raise ValueError(
                    "El efectivo del corte general debe coincidir con "
                    "el efectivo contado en el corte de caja chica."
                )
            rows.append((
                day, method, opening, row["entradas_centavos"],
                row["compras_centavos"], row["otras_salidas_centavos"],
                expected, actual, actual - expected,
            ))
        try:
            cursor.execute(
                "INSERT INTO cortes_generales(fecha, notas) VALUES (?, ?)",
                (day, notes.strip()),
            )
            cursor.executemany(
                """INSERT INTO detalle_corte_general
                   (fecha, metodo_pago, saldo_inicial_centavos, entradas_centavos,
                    compras_centavos, otras_salidas_centavos,
                    saldo_esperado_centavos, saldo_real_centavos, diferencia_centavos)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            self.database.commit()
        except Exception:
            self.database.rollback()
            raise
        return self.get_closing(day)
