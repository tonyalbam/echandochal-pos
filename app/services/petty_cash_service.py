"""Caja chica: saldos arrastrados, gastos y cierres diarios irreversibles.

Los cobros en efectivo son los montos aplicados a ventas, NO el efectivo
recibido: el cambio al cliente ya está descontado del importe de venta.
"""
from datetime import date
import json
from decimal import Decimal
from app.services.payment_allocation import cents


class PettyCashService:
    EXPENSE_TYPES = ("Gastos Fijos", "Gastos variables")

    def __init__(self, database):
        self.database = database

    @staticmethod
    def _date(value):
        return date.fromisoformat(value).isoformat()

    def get_closing(self, day):
        day = self._date(day)
        cursor = self.database.cursor()
        cursor.execute("SELECT * FROM cierres_caja WHERE fecha = ?", (day,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def _last_closing_before(self, day):
        cursor = self.database.cursor()
        cursor.execute(
            """SELECT fecha, saldo_contado_centavos FROM cierres_caja
               WHERE fecha < ? ORDER BY fecha DESC LIMIT 1""", (day,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_expenses(self, day):
        day = self._date(day)
        cursor = self.database.cursor()
        cursor.execute(
            """SELECT id, fecha, tipo, descripcion, monto_centavos,
                      creado_en FROM gastos_caja
               WHERE fecha = ? AND anulado = 0 ORDER BY id""", (day,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def _cash_sales_cents(self, day):
        # resumen_pagos_venta trata ventas mixtas, antiguas y comisiones.
        # Una venta en efectivo de $50 con $100 recibido y $50 de cambio
        # incrementa el saldo de la caja en exactamente $50.
        cursor = self.database.cursor()
        cursor.execute(
            """SELECT COALESCE(SUM(p.ventas), 0)
               FROM resumen_pagos_venta p
               JOIN ventas v ON v.id = p.venta_id
               WHERE v.fecha = ? AND v.cancelada = 0
                 AND p.metodo_pago = 'Efectivo'""",
            (day,),
        )
        return cents(cursor.fetchone()[0])

    def get_initial_fund(self):
        cursor = self.database.cursor()
        cursor.execute("SELECT * FROM fondo_inicial_caja WHERE id = 1")
        row = cursor.fetchone()
        return dict(row) if row else None

    def register_initial_fund(self, day, amount):
        """Ingreso inicial único, documentado y anterior al primer cierre."""
        day = self._date(day)
        amount_cents = cents(amount)
        if amount_cents <= 0:
            raise ValueError("El fondo inicial debe ser mayor a cero.")
        if day > date.today().isoformat():
            raise ValueError("No puedes registrar un fondo en una fecha futura.")
        if self.get_initial_fund():
            raise ValueError("El fondo inicial ya está registrado.")
        cursor = self.database.cursor()
        cursor.execute("SELECT 1 FROM cierres_caja LIMIT 1")
        if cursor.fetchone():
            raise ValueError(
                "Ya existe un corte confirmado. El fondo inicial no puede cambiarse."
            )
        cursor.execute(
            "INSERT INTO fondo_inicial_caja (id, fecha, monto_centavos) "
            "VALUES (1, ?, ?)", (day, amount_cents)
        )
        self.database.commit()
        return amount_cents

    def get_summary(self, day):
        day = self._date(day)
        last = self._last_closing_before(day)
        fund = self.get_initial_fund()
        opening = int(last["saldo_contado_centavos"]) if last else (
            int(fund["monto_centavos"])
            if fund and day >= fund["fecha"] else 0
        )
        sales = self._cash_sales_cents(day)
        expenses = self.get_expenses(day)
        withdrawals = sum(item["monto_centavos"] for item in expenses)
        expected = opening + sales - withdrawals
        return {
            "fecha": day, "saldo_inicial_centavos": opening,
            "cierre_anterior": last["fecha"] if last else None,
            "fondo_inicial": fund,
            "ventas_efectivo_centavos": sales,
            "gastos_centavos": withdrawals,
            "saldo_esperado_centavos": expected,
            "gastos": expenses,
            "cierre": self.get_closing(day),
        }

    def _assert_day_editable(self, day):
        if self.get_closing(day):
            raise ValueError("Este corte diario ya fue confirmado y no se puede modificar.")
        cursor = self.database.cursor()
        cursor.execute("SELECT fecha FROM cierres_caja WHERE fecha > ? LIMIT 1", (day,))
        if cursor.fetchone():
            raise ValueError(
                "No se puede modificar un día anterior a un cierre confirmado posterior."
            )
        if day > date.today().isoformat():
            raise ValueError("No se permiten gastos ni cierres en fechas futuras.")

    def add_expense(self, day, kind, description, amount):
        day = self._date(day)
        if kind not in self.EXPENSE_TYPES:
            raise ValueError("Selecciona Gastos Fijos o Gastos variables.")
        description = description.strip()
        if not description or len(description) > 250:
            raise ValueError("La descripción debe tener de 1 a 250 caracteres.")
        amount_cents = cents(amount)
        if amount_cents <= 0:
            raise ValueError("El gasto debe ser mayor a cero.")
        self._assert_day_editable(day)
        summary = self.get_summary(day)
        if amount_cents > summary["saldo_esperado_centavos"]:
            raise ValueError("El retiro excede el efectivo disponible en caja chica.")
        cursor = self.database.cursor()
        cursor.execute(
            """INSERT INTO gastos_caja(fecha, tipo, descripcion, monto_centavos)
               VALUES (?, ?, ?, ?)""",
            (day, kind, description, amount_cents),
        )
        expense_id = cursor.lastrowid
        self.database.commit()
        return expense_id

    def delete_expense(self, day, expense_id):
        day = self._date(day)
        self._assert_day_editable(day)
        cursor = self.database.cursor()
        cursor.execute(
            """UPDATE gastos_caja SET anulado = 1,
                      anulado_en = CURRENT_TIMESTAMP
                 WHERE fecha = ? AND id = ? AND anulado = 0""",
            (day, int(expense_id)),
        )
        if cursor.rowcount != 1:
            raise ValueError("El gasto no existe para el día seleccionado.")
        self.database.commit()

    def confirm_closing(self, day, counts, loose_change):
        day = self._date(day)
        self._assert_day_editable(day)
        # Calcular centavos exactos y rechazar valores inválidos.
        from app.services.cash_closing_service import CashClosingService
        service = CashClosingService(self.database)
        counted = 0
        for kind, denom in service.BILL_DENOMINATIONS:
            number = counts.get((kind, denom), 0)
            if isinstance(number, bool) or not isinstance(number, int):
                raise ValueError("La cantidad de billetes debe ser entera.")
            if number < 0 or number > 9999:
                raise ValueError("Cantidad de billetes fuera de rango.")
            counted += cents(Decimal(str(denom)) * number)
        counted += cents(loose_change)
        # Si existe un cierre previo, no saltar fechas intermedias
        # con entradas o salidas de efectivo aún sin cerrar.
        previous = self._last_closing_before(day)
        if previous:
            cursor = self.database.cursor()
            cursor.execute(
                """SELECT MIN(v.fecha)
                   FROM resumen_pagos_venta p
                   JOIN ventas v ON v.id = p.venta_id
                   WHERE v.fecha > ? AND v.fecha < ?
                     AND v.cancelada = 0 AND p.metodo_pago = 'Efectivo'
                     AND p.ventas > 0""",
                (previous["fecha"], day),
            )
            pending_sale = cursor.fetchone()[0]
            cursor.execute(
                """SELECT MIN(fecha) FROM gastos_caja
                   WHERE fecha > ? AND fecha < ? AND anulado = 0""",
                (previous["fecha"], day),
            )
            pending_expense = cursor.fetchone()[0]
            if pending_sale or pending_expense:
                first_pending = min(
                    value for value in (pending_sale, pending_expense)
                    if value is not None
                )
                raise ValueError(
                    f"Hay movimientos de efectivo del {first_pending} "
                    "sin corte confirmado. Cierra ese día primero."
                )
        summary = self.get_summary(day)
        expected = summary["saldo_esperado_centavos"]
        if expected < 0:
            raise ValueError("El saldo esperado es negativo. Revisa los gastos.")
        if counted != expected:
            difference = (counted - expected) / 100
            raise ValueError(
                f"El arqueo no cuadra (diferencia: $ {difference:,.2f}). "
                "Corrige la captura antes de confirmar el corte."
            )
        cursor = self.database.cursor()
        denominations = {
            str(int(denom)): counts.get((kind, denom), 0)
            for kind, denom in service.BILL_DENOMINATIONS
        }
        try:
            cursor.execute(
                """INSERT INTO cierres_caja
                   (fecha, saldo_inicial_centavos, ventas_efectivo_centavos,
                    gastos_centavos, saldo_esperado_centavos, saldo_contado_centavos,
                    conteos_json, morralla_centavos)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (day, summary["saldo_inicial_centavos"],
                 summary["ventas_efectivo_centavos"], summary["gastos_centavos"],
                 expected, counted, json.dumps(denominations), cents(loose_change)),
            )
            self.database.commit()
        except Exception:
            self.database.rollback()
            raise
        return self.get_closing(day)
