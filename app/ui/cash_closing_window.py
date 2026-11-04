from app.ui.theme import theme_colors
from PySide6.QtCore import QDate, Qt, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDateEdit,
    QComboBox,
    QScrollArea,
    QLineEdit,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import Database
from app.services.cash_closing_service import CashClosingService
from app.services.petty_cash_service import PettyCashService


class ClearOnFocusAmount(QLineEdit):
    """Cantidad editable sin flechas, que se limpia al recibir el foco.

    El campo vacío representa cero solo para el cálculo y los exportables.
    """

    def __init__(self, *, decimals: int = 0, parent=None) -> None:
        super().__init__(parent)
        if decimals not in (0, 2):
            raise ValueError("Solo se permiten cantidades enteras o monetarias.")
        self.decimals = decimals
        pattern = (
            r"\d{0,6}(?:\.\d{0,2})?" if decimals else r"\d{0,4}"
        )
        self.setValidator(
            QRegularExpressionValidator(QRegularExpression(pattern), self)
        )
        self.setPlaceholderText("Escribe el monto" if decimals else "Cantidad")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setMinimumHeight(35)
        self.setMinimumWidth(110)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.clear()

    def amount(self):
        value = self.text().strip()
        if not value:
            return 0.0 if self.decimals else 0
        return float(value) if self.decimals else int(value)


class CashClosingWindow(QWidget):
    """Resumen y exportación del corte diario."""

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.service = CashClosingService(database)
        self.petty_cash = PettyCashService(database)
        self._create_ui()
        self.refresh()

    def _create_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(25, 20, 25, 25)
        layout.setSpacing(14)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        title = QLabel("Corte diario")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(title)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Fecha:"))
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        self.date.dateChanged.connect(self._date_changed)
        controls.addWidget(self.date)

        refresh_button = QPushButton("Actualizar")
        refresh_button.clicked.connect(self.refresh)
        controls.addWidget(refresh_button)
        controls.addStretch()

        excel_button = QPushButton("Exportar Excel")
        excel_button.clicked.connect(self._export_excel)
        controls.addWidget(excel_button)
        pdf_button = QPushButton("Exportar PDF")
        pdf_button.clicked.connect(self._export_pdf)
        controls.addWidget(pdf_button)
        layout.addLayout(controls)

        self.table = QTableWidget(3, 5)
        self.table.setHorizontalHeaderLabels([
            "Forma de pago", "Tickets", "Ventas", "Comisiones", "Dinero neto"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        summary_grid = QGridLayout()
        self.values: dict[str, QLabel] = {}
        fields = (
            ("total_ventas", "TOTAL VENTAS"),
            ("comisiones", "Comisiones Mercado Libre"),
            ("dinero_neto", "DINERO NETO"),
            ("numero_tickets", "Número de tickets"),
            ("productos_vendidos", "Productos vendidos"),
            ("utilidad", "Utilidad del día"),
        )
        for index, (key, label) in enumerate(fields):
            title_label = QLabel(label)
            title_label.setStyleSheet("font-weight: bold;")
            value_label = QLabel("$0.00")
            value_label.setStyleSheet("font-size: 20px; font-weight: bold;")
            row, column = divmod(index, 3)
            container = QVBoxLayout()
            container.addWidget(title_label)
            container.addWidget(value_label)
            summary_grid.addLayout(container, row, column)
            self.values[key] = value_label
        layout.addLayout(summary_grid)

        cash_group = QGroupBox("Arqueo manual de efectivo")
        cash_layout = QGridLayout(cash_group)
        cash_layout.addWidget(QLabel("Tipo"), 0, 0)
        cash_layout.addWidget(QLabel("Denominación"), 0, 1)
        cash_layout.addWidget(QLabel("Cantidad"), 0, 2)
        cash_layout.addWidget(QLabel("Importe"), 0, 3)
        self.cash_inputs = {}
        self.cash_amounts = {}
        for row, (kind, denomination) in enumerate(
            self.service.BILL_DENOMINATIONS, start=1
        ):
            cash_layout.addWidget(QLabel(kind), row, 0)
            cash_layout.addWidget(QLabel(f"$ {denomination:,.2f}"), row, 1)
            quantity = ClearOnFocusAmount()
            quantity.textChanged.connect(self._update_cash_reconciliation)
            cash_layout.addWidget(quantity, row, 2)
            amount = QLabel("$ 0.00")
            amount.setAlignment(Qt.AlignmentFlag.AlignRight)
            cash_layout.addWidget(amount, row, 3)
            key = (kind, denomination)
            self.cash_inputs[key] = quantity
            self.cash_amounts[key] = amount

        cash_layout.addWidget(QLabel("Morralla"), 1, 5)
        self.loose_change = ClearOnFocusAmount(decimals=2)
        self.loose_change.textChanged.connect(self._update_cash_reconciliation)
        cash_layout.addWidget(self.loose_change, 1, 6, 1, 2)

        self.cash_expected = QLabel("$ 0.00")
        self.cash_counted = QLabel("$ 0.00")
        self.cash_difference = QLabel("$ 0.00")
        self.cash_status = QLabel("PENDIENTE")
        summary_row = 8
        for column, (title, value) in enumerate((
            ("Efectivo esperado", self.cash_expected),
            ("Efectivo contado", self.cash_counted),
            ("Diferencia", self.cash_difference),
            ("Estado", self.cash_status),
        )):
            cash_layout.addWidget(QLabel(title), summary_row, column * 2)
            value.setStyleSheet("font-size: 16px; font-weight: bold;")
            cash_layout.addWidget(value, summary_row, column * 2 + 1)
        layout.addWidget(cash_group)

        # Registro de retiros de efectivo; no altera las compras ni las ventas.
        expenses_group = QGroupBox("Gastos operativos de caja chica")
        expenses_layout = QVBoxLayout(expenses_group)
        expenses_form = QHBoxLayout()
        self.expense_type = QComboBox()
        self.expense_type.addItems(self.petty_cash.EXPENSE_TYPES)
        self.expense_description = QLineEdit()
        self.expense_description.setPlaceholderText("Descripción del gasto")
        self.expense_description.setMaxLength(250)
        self.expense_amount = ClearOnFocusAmount(decimals=2)
        self.expense_amount.setPlaceholderText("Monto en efectivo")
        self.add_expense_button = QPushButton("Registrar gasto")
        self.add_expense_button.clicked.connect(self._register_expense)
        expenses_form.addWidget(QLabel("Tipo:"))
        expenses_form.addWidget(self.expense_type)
        expenses_form.addWidget(QLabel("Descripción:"))
        expenses_form.addWidget(self.expense_description, 1)
        expenses_form.addWidget(QLabel("Monto:"))
        expenses_form.addWidget(self.expense_amount)
        expenses_form.addWidget(self.add_expense_button)
        expenses_layout.addLayout(expenses_form)
        self.expenses_table = QTableWidget(0, 4)
        self.expenses_table.setHorizontalHeaderLabels(
            ["ID", "Tipo", "Descripción", "Monto retirado"]
        )
        self.expenses_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.expenses_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.expenses_table.setColumnHidden(0, True)
        self.expenses_table.horizontalHeader().setStretchLastSection(True)
        self.expenses_table.setMinimumHeight(135)
        expenses_layout.addWidget(self.expenses_table)
        expense_actions = QHBoxLayout()
        self.remove_expense_button = QPushButton("Eliminar gasto seleccionado")
        self.remove_expense_button.clicked.connect(self._remove_expense)
        expense_actions.addWidget(self.remove_expense_button)
        expense_actions.addStretch()
        expenses_layout.addLayout(expense_actions)
        layout.addWidget(expenses_group)

        carryover_group = QGroupBox("Control de caja chica y confirmación del corte")
        carryover_layout = QGridLayout(carryover_group)
        self.opening_cash = QLabel("$ 0.00")
        self.cash_sales = QLabel("$ 0.00")
        self.operating_expenses = QLabel("$ 0.00")
        self.closing_state = QLabel("Corte pendiente de confirmación")
        for index, (label, widget) in enumerate((
            ("Saldo inicial (último corte confirmado)", self.opening_cash),
            ("Entradas por ventas en efectivo (cambio descontado)", self.cash_sales),
            ("Salidas por gastos operativos", self.operating_expenses),
            ("Estado del corte", self.closing_state),
        )):
            carryover_layout.addWidget(QLabel(label), index, 0)
            carryover_layout.addWidget(widget, index, 1)
        fund_row = QHBoxLayout()
        self.initial_fund_amount = ClearOnFocusAmount(decimals=2)
        self.initial_fund_amount.setPlaceholderText("Fondo inicial en efectivo")
        self.initial_fund_button = QPushButton("Registrar fondo inicial (una vez)")
        self.initial_fund_button.clicked.connect(self._register_initial_fund)
        fund_row.addWidget(self.initial_fund_amount)
        fund_row.addWidget(self.initial_fund_button)
        carryover_layout.addWidget(QLabel("Fondo previo a primer corte"), 4, 0)
        carryover_layout.addLayout(fund_row, 4, 1)
        self.confirm_closing_button = QPushButton("Confirmar el corte diario")
        self.confirm_closing_button.clicked.connect(self._confirm_closing)
        carryover_layout.addWidget(self.confirm_closing_button, 5, 0, 1, 2)
        layout.addWidget(carryover_group)
        layout.addStretch()

    def _selected_date(self) -> str:
        return self.date.date().toString("yyyy-MM-dd")

    def _date_changed(self) -> None:
        for widget in self.cash_inputs.values():
            widget.blockSignals(True)
            widget.clear()
            widget.blockSignals(False)
        self.loose_change.blockSignals(True)
        self.loose_change.clear()
        self.loose_change.blockSignals(False)
        self.refresh()

    def refresh(self) -> None:
        data = self.service.get_daily_closing(self._selected_date())
        for row, payment in enumerate(data["formas_pago"]):
            values = (
                payment["metodo_pago"], payment["tickets"],
                f"$ {payment['ventas']:,.2f}",
                f"$ {payment['comisiones']:,.2f}",
                f"$ {payment['dinero_neto']:,.2f}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column > 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, column, item)

        for key in ("total_ventas", "comisiones", "dinero_neto", "utilidad"):
            self.values[key].setText(f"$ {data[key]:,.2f}")
        self.values["numero_tickets"].setText(str(data["numero_tickets"]))
        self.values["productos_vendidos"].setText(
            f"{data['productos_vendidos']:g}"
        )
        self._refresh_petty_cash()
        self._update_cash_reconciliation()

    def _refresh_petty_cash(self) -> None:
        summary = self.petty_cash.get_summary(self._selected_date())
        self.opening_cash.setText(
            f"$ {summary['saldo_inicial_centavos'] / 100:,.2f}"
        )
        self.cash_sales.setText(
            f"$ {summary['ventas_efectivo_centavos'] / 100:,.2f}"
        )
        self.operating_expenses.setText(
            f"$ {summary['gastos_centavos'] / 100:,.2f}"
        )
        self.expenses_table.setRowCount(0)
        for index, expense in enumerate(summary["gastos"]):
            self.expenses_table.insertRow(index)
            entries = (
                expense["id"], expense["tipo"], expense["descripcion"],
                f"$ {expense['monto_centavos'] / 100:,.2f}"
            )
            for col, value in enumerate(entries):
                self.expenses_table.setItem(index, col, QTableWidgetItem(str(value)))
        closed = summary["cierre"] is not None
        self.closing_state.setText(
            f"CONFIRMADO: {summary['cierre']['confirmado_en']}"
            if closed else "Pendiente de confirmación"
        )
        self.confirm_closing_button.setEnabled(not closed)
        can_fund = not closed and summary["fondo_inicial"] is None
        self.initial_fund_amount.setEnabled(can_fund)
        self.initial_fund_button.setEnabled(can_fund)
        self.add_expense_button.setEnabled(not closed)
        self.remove_expense_button.setEnabled(not closed)
        self.expense_type.setEnabled(not closed)
        self.expense_description.setEnabled(not closed)
        self.expense_amount.setEnabled(not closed)
        for field in self.cash_inputs.values():
            field.setReadOnly(closed)
        self.loose_change.setReadOnly(closed)

    def _register_initial_fund(self) -> None:
        amount = self.initial_fund_amount.amount()
        if amount <= 0:
            QMessageBox.warning(
                self, "Fondo inicial", "Ingresa el monto inicial en efectivo."
            )
            return
        confirm = QMessageBox.question(
            self, "Registrar fondo inicial",
            f"¿Registrar un fondo inicial de $ {amount:,.2f}?\n\n"
            "Solo se puede registrar una vez, antes del primer corte confirmado. "
            "Este importe se sumará al efectivo disponible de caja chica.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.petty_cash.register_initial_fund(self._selected_date(), amount)
        except ValueError as error:
            QMessageBox.warning(self, "Fondo no registrado", str(error))
            return
        self.initial_fund_amount.clear()
        self._refresh_petty_cash()
        self._update_cash_reconciliation()

    def _register_expense(self) -> None:
        try:
            self.petty_cash.add_expense(
                self._selected_date(), self.expense_type.currentText(),
                self.expense_description.text(), self.expense_amount.amount()
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "No se pudo registrar el gasto", str(error))
            return
        self.expense_description.clear()
        self.expense_amount.clear()
        self._refresh_petty_cash()
        self._update_cash_reconciliation()

    def _remove_expense(self) -> None:
        row = self.expenses_table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Selecciona un gasto", "Selecciona el gasto que deseas eliminar."
            )
            return
        expense_id = int(self.expenses_table.item(row, 0).text())
        reply = QMessageBox.question(
            self, "Eliminar gasto",
            "¿Eliminar este gasto antes de confirmar el corte?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.petty_cash.delete_expense(self._selected_date(), expense_id)
        except ValueError as error:
            QMessageBox.warning(self, "No se pudo eliminar", str(error))
            return
        self._refresh_petty_cash()
        self._update_cash_reconciliation()

    def _confirm_closing(self) -> None:
        cash = self.service.calculate_cash_reconciliation(
            self._selected_date(), self._cash_counts(), self.loose_change.amount()
        )
        if cash["estado"] != "CUADRA":
            QMessageBox.warning(
                self, "El arqueo no cuadra",
                "El efectivo contado debe coincidir con el saldo esperado "
                "antes de confirmar el corte. Revisa billetes, morralla y gastos."
            )
            return
        reply = QMessageBox.question(
            self, "Confirmar el corte diario",
            f"¿Confirmar el corte de {self._selected_date()} por "
            f"$ {cash['efectivo_contado']:,.2f}?\n\n"
            "Este monto será el saldo inicial de la caja chica para el "
            "siguiente día. Una vez confirmado no se podrán agregar ni "
            "eliminar gastos de este día.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.petty_cash.confirm_closing(
                self._selected_date(), self._cash_counts(), self.loose_change.amount()
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "No se pudo cerrar", str(error))
            return
        self._refresh_petty_cash()
        QMessageBox.information(
            self, "Corte confirmado",
            "Corte guardado. El efectivo contado se trasladará como saldo "
            "inicial al siguiente día."
        )

    def _cash_counts(self) -> dict[tuple[str, float], int]:
        return {
            key: widget.amount()
            for key, widget in self.cash_inputs.items()
        }

    def _update_cash_reconciliation(self) -> None:
        cash = self.service.calculate_cash_reconciliation(
            self._selected_date(), self._cash_counts(), self.loose_change.amount()
        )
        for row in cash["denominaciones"]:
            key = (row["tipo"], row["denominacion"])
            self.cash_amounts[key].setText(f"$ {row['importe']:,.2f}")
        self.cash_expected.setText(f"$ {cash['efectivo_esperado']:,.2f}")
        self.cash_counted.setText(f"$ {cash['efectivo_contado']:,.2f}")
        self.cash_difference.setText(f"$ {cash['diferencia']:,.2f}")
        self.cash_status.setText(cash["estado"])
        self._cash_is_balanced = cash["estado"] == "CUADRA"
        self.apply_theme(getattr(self, "_dark_mode", False))

    def apply_theme(self, dark: bool) -> None:
        self._dark_mode = bool(dark)
        if not hasattr(self, "_cash_is_balanced"):
            return
        colors = theme_colors(dark)
        color = colors["success"] if self._cash_is_balanced else colors["danger"]
        self.cash_status.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {color};"
        )

    def _export_excel(self) -> None:
        date = self._selected_date()
        destination, _ = QFileDialog.getSaveFileName(
            self, "Exportar corte diario", f"corte_{date}.xlsx",
            "Archivos de Excel (*.xlsx)",
        )
        if destination:
            self._run_export(self.service.export_excel, date, destination)

    def _export_pdf(self) -> None:
        date = self._selected_date()
        destination, _ = QFileDialog.getSaveFileName(
            self, "Exportar corte diario", f"corte_{date}.pdf",
            "Documento PDF (*.pdf)",
        )
        if destination:
            self._run_export(self.service.export_pdf, date, destination)

    def _run_export(self, exporter, date: str, destination: str) -> None:
        try:
            output_path = exporter(
                date, destination, self._cash_counts(), self.loose_change.amount()
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "No se pudo exportar", str(error))
            return
        QMessageBox.information(
            self, "Corte exportado",
            f"El corte se guardó correctamente en:\n{output_path}",
        )
