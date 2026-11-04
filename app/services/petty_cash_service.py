"""Caja chica: saldos arrastrados, gastos y cierres diarios irreversibles.

Los cobros en efectivo son los montos aplicados a ventas, NO el efectivo
recibido: el cambio al cliente ya está descontado del importe de venta.
"""
from datetime import date
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
               WHERE fecha = ? ORDER BY id""", (day,)
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

    def get_summary(self, day):
        day = self._date(day)
        last = self._last_closing_before(day)
        opening = int(last["saldo_contado_centavos"]) if last else 0
        sales = self._cash_sales_cents(day)
        expenses = self.get_expenses(day)
        withdrawals = sum(item["monto_centavos"] for item in expenses)
        expected = opening + sales - withdrawals
        return {
            "fecha": day, "saldo_inicial_centavos": opening,
            "cierre_anterior": last["fecha"] if last else None,
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
            "DELETE FROM gastos_caja WHERE fecha = ? AND id = ?",
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
        try:
            cursor.execute(
                """INSERT INTO cierres_caja
                   (fecha, saldo_inicial_centavos, ventas_efectivo_centavos,
                    gastos_centavos, saldo_esperado_centavos, saldo_contado_centavos)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (day, summary["saldo_inicial_centavos"],
                 summary["ventas_efectivo_centavos"], summary["gastos_centavos"],
                 expected, counted),
            )
            self.database.commit()
        except Exception:
            self.database.rollback()
            raise
        return self.get_closing(day)
