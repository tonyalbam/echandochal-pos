from app.ui.theme import theme_colors
from PySide6.QtCore import QDate, QEvent, Qt, QRegularExpression, QTimer
from PySide6.QtGui import QCursor, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDateEdit,
    QApplication,
    QFrame,
    QDialog,
    QComboBox,
    QScrollArea,
    QLineEdit,
    QFileDialog,
    QGridLayout,
    QHeaderView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QTableWidgetItem,
    QSizePolicy,
    QAbstractItemView,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import Database
from app.services.cash_closing_service import CashClosingService
from app.services.petty_cash_service import PettyCashService
from app.services.general_closing_service import GeneralClosingService
from app.ui.sale_window import PaymentAmountInput


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
        self.general_service = GeneralClosingService(database)
        self._profit_popup = None
        self._profit_hover_targets = []
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

        # Tres formas de pago, siempre visibles. Una tabla flexible en ancho
        # y de altura fija evita que QScrollArea comprima las filas a cero.
        self.table = QTableWidget(len(self.service.PAYMENT_METHODS), 5)
        self.table.setHorizontalHeaderLabels([
            "Forma de pago", "Tickets", "Ventas", "Comisiones", "Dinero neto"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(34)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(95)
        header.setFixedHeight(34)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        table_height = (
            header.height()
            + self.table.verticalHeader().defaultSectionSize()
            * len(self.service.PAYMENT_METHODS)
            + 2 * self.table.frameWidth()
            + 4
        )
        self.table.setFixedHeight(table_height)
        layout.addWidget(self.table)

        summary_grid = QGridLayout()
        self.values: dict[str, QLabel] = {}
        fields = (
            ("total_ventas", "TOTAL VENTAS"),
            ("comisiones", "Comisiones Mercado Libre"),
            ("dinero_neto", "DINERO NETO"),
            ("numero_tickets", "Número de tickets"),
            ("productos_vendidos", "Productos vendidos"),
            ("utilidad", "UTILIDAD OPERATIVA DEL DÍA"),
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
            if key == "utilidad":
                self._profit_hover_targets = [title_label, value_label]
                for widget in self._profit_hover_targets:
                    widget.setMouseTracking(True)
                    widget.setCursor(Qt.CursorShape.WhatsThisCursor)
                    widget.installEventFilter(self)
        layout.addLayout(summary_grid)

        # Las pestañas empiezan exactamente donde antes comenzaba el arqueo.
        # La vista de entradas/salidas es la primera y predeterminada.
        self.tabs = QTabWidget()
        self.tabs.setObjectName("daily_closing_tabs")
        layout.addWidget(self.tabs, 1)

        self.general_flows_tab = QWidget()
        self.general_flows_layout = QVBoxLayout(self.general_flows_tab)
        self.tabs.addTab(self.general_flows_tab, "Corte general entradas/salidas")

        self.cash_tab = QWidget()
        self.cash_tab_layout = QVBoxLayout(self.cash_tab)
        self.tabs.addTab(self.cash_tab, "Arqueo manual de efectivo")

        self.petty_tab = QWidget()
        self.petty_tab_layout = QVBoxLayout(self.petty_tab)
        self.tabs.addTab(self.petty_tab, "Caja chica")

        self.general_cut_tab = QWidget()
        self.general_cut_layout = QVBoxLayout(self.general_cut_tab)
        self.tabs.addTab(self.general_cut_tab, "Corte general")
        self.tabs.setCurrentIndex(0)

        accumulated_group = QGroupBox("Movimientos acumulados por concepto")
        accumulated_layout = QVBoxLayout(accumulated_group)
        self.concepts_table = QTableWidget(len(self.general_service.CONCEPTS), 4)
        self.concepts_table.setObjectName("accumulated_concepts")
        self.concepts_table.setHorizontalHeaderLabels((
            "Concepto", "Tipo", "Importe del día", "Acumulado hasta la fecha",
        ))
        self.concepts_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.concepts_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.concepts_table.verticalHeader().hide()
        self.concepts_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.concepts_table.setMinimumHeight(330)
        accumulated_layout.addWidget(self.concepts_table)
        self.accumulated_summary = QLabel()
        self.accumulated_summary.setWordWrap(True)
        self.accumulated_summary.setStyleSheet(
            "font-size: 14px; font-weight: bold;"
        )
        accumulated_layout.addWidget(self.accumulated_summary)
        self.general_flows_layout.addWidget(accumulated_group)

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
        self.cash_tab_layout.addWidget(cash_group)
        self.cash_tab_layout.addStretch()

        # Flujos observados por medio de pago: no equivalen a los saldos
        # bancarios sin un saldo inicial y conciliación de cuentas.
        flows_group = QGroupBox("Movimientos del día por medio de pago")
        flows_layout = QVBoxLayout(flows_group)
        self.payment_flows = QTableWidget(3, 4)
        self.payment_flows.setHorizontalHeaderLabels((
            "Medio de pago", "Entradas por ventas",
            "Salidas por compras", "Flujo neto del día",
        ))
        self.payment_flows.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.payment_flows.verticalHeader().hide()
        self.payment_flows.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.payment_flows.setFixedHeight(160)
        flows_layout.addWidget(self.payment_flows)
        flows_layout.addWidget(QLabel(
            "Los flujos de tarjeta y transferencia no son saldos bancarios "
            "hasta conciliar el saldo inicial y las comisiones."
        ))
        self.general_flows_layout.addWidget(flows_group)
        self.general_flows_layout.addStretch()

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
        self.petty_tab_layout.addWidget(expenses_group)

        carryover_group = QGroupBox("Control de caja chica y confirmación del corte")
        carryover_layout = QGridLayout(carryover_group)
        self.opening_cash = QLabel("$ 0.00")
        self.cash_sales = QLabel("$ 0.00")
        self.operating_expenses = QLabel("$ 0.00")
        self.cash_purchases = QLabel("$ 0.00")
        self.closing_state = QLabel("Corte pendiente de confirmación")
        for index, (label, widget) in enumerate((
            ("Saldo inicial (último corte confirmado)", self.opening_cash),
            ("Entradas por ventas en efectivo (cambio descontado)", self.cash_sales),
            ("Salidas por compras de mercancía en efectivo", self.cash_purchases),
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
        carryover_layout.addWidget(QLabel("Fondo previo a primer corte"), 5, 0)
        carryover_layout.addLayout(fund_row, 5, 1)
        self.confirm_closing_button = QPushButton("Confirmar el corte diario")
        self.confirm_closing_button.clicked.connect(self._confirm_closing)
        carryover_layout.addWidget(self.confirm_closing_button, 6, 0, 1, 2)
        self.petty_tab_layout.addWidget(carryover_group)
        self.petty_tab_layout.addStretch()

        self._create_general_cut_form()
        self._create_profit_hover_popup()

    def _create_general_cut_form(self) -> None:
        """Captura manual y conciliación del saldo real por medio de pago."""
        hint = QLabel(
            "El efectivo se concilia contra el corte confirmado de caja chica. "
            "Para tarjeta y transferencia, el primer corte requiere registrar "
            "el saldo inicial real. Los siguientes utilizan el saldo real "
            "confirmado del corte general anterior."
        )
        hint.setWordWrap(True)
        self.general_cut_layout.addWidget(hint)
        group = QGroupBox("Corte general por medio de pago")
        form = QGridLayout(group)
        headings = (
            "Medio", "Saldo inicial", "Entradas por ventas",
            "Salidas por compras", "Otras salidas",
            "Saldo esperado", "Saldo real", "Diferencia",
        )
        for col, text in enumerate(headings):
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet("font-weight: bold;")
            form.addWidget(label, 0, col)

        self.general_openings = {}
        self.general_initial_labels = {}
        self.general_actual = {}
        self.general_real_labels = {}
        self.general_summary_cells = {}
        for row, method in enumerate(self.general_service.METHODS, start=1):
            form.addWidget(QLabel(method), row, 0)
            starting = QLabel("Pendiente")
            self.general_initial_labels[method] = starting
            opening_field = PaymentAmountInput(self)
            opening_field.setAccessibleName(
                f"Saldo inicial de {method}"
            )
            opening_field.textChanged.connect(self._update_general_preview)
            self.general_openings[method] = opening_field
            if method == "Efectivo":
                form.addWidget(starting, row, 1)
                opening_field.hide()
            else:
                # Mismo espacio de cuadrícula: campo sólo para primer corte.
                starting_container = QWidget()
                starting_layout = QVBoxLayout(starting_container)
                starting_layout.setContentsMargins(0, 0, 0, 0)
                starting_layout.addWidget(starting)
                starting_layout.addWidget(opening_field)
                form.addWidget(starting_container, row, 1)
            for col, key in enumerate((
                "entradas_centavos", "compras_centavos",
                "otras_salidas_centavos", "saldo_esperado_centavos",
            ), start=2):
                value = QLabel("Pendiente")
                value.setAlignment(Qt.AlignmentFlag.AlignRight)
                form.addWidget(value, row, col)
                self.general_summary_cells[(method, key)] = value

            actual = PaymentAmountInput(self)
            actual.setAccessibleName(f"Saldo real de {method}")
            actual.textChanged.connect(self._update_general_preview)
            actual_label = QLabel("")
            self.general_actual[method] = actual
            self.general_real_labels[method] = actual_label
            real_container = QWidget()
            real_layout = QVBoxLayout(real_container)
            real_layout.setContentsMargins(0, 0, 0, 0)
            real_layout.addWidget(actual_label)
            real_layout.addWidget(actual)
            form.addWidget(real_container, row, 6)

            difference = QLabel("Pendiente")
            difference.setAlignment(Qt.AlignmentFlag.AlignRight)
            form.addWidget(difference, row, 7)
            self.general_summary_cells[(method, "diferencia_centavos")] = difference

        self.general_cut_layout.addWidget(group)
        notes_line = QHBoxLayout()
        notes_line.addWidget(QLabel("Observaciones:"))
        self.general_notes = QLineEdit()
        self.general_notes.setPlaceholderText(
            "Opcional: explicación de diferencias o movimientos"
        )
        self.general_notes.setMaxLength(500)
        notes_line.addWidget(self.general_notes, 1)
        self.general_cut_layout.addLayout(notes_line)
        self.general_cut_status = QLabel("Corte general pendiente")
        self.general_cut_status.setWordWrap(True)
        self.general_cut_layout.addWidget(self.general_cut_status)
        self.confirm_general_button = QPushButton("Confirmar corte general")
        self.confirm_general_button.clicked.connect(self._confirm_general_closing)
        self.general_cut_layout.addWidget(self.confirm_general_button)
        self.general_cut_layout.addStretch()

    @staticmethod
    def _optional_amount(field):
        value = field.text().strip()
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _money_centavos(value):
        return "Por conciliar" if value is None else f"$ {value / 100:,.2f}"

    def _refresh_concept_movements(self) -> None:
        movements = self.general_service.get_concept_movements(
            self._selected_date()
        )
        daily_income = daily_out = cumulative_income = cumulative_out = 0
        for row, movement in enumerate(movements):
            daily = movement["dia_centavos"]
            accrued = movement["acumulado_centavos"]
            if movement["tipo"] == "Entrada":
                daily_income += daily
                cumulative_income += accrued
            else:
                daily_out += daily
                cumulative_out += accrued
            values = (
                movement["concepto"], movement["tipo"],
                self._money_centavos(daily), self._money_centavos(accrued),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column >= 2:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                self.concepts_table.setItem(row, column, cell)
        self.accumulated_summary.setText(
            f"Hoy: entradas {self._money_centavos(daily_income)} | "
            f"salidas {self._money_centavos(daily_out)} | "
            f"flujo neto {self._money_centavos(daily_income - daily_out)}    "
            f"Acumulado hasta {self._selected_date()}: "
            f"entradas {self._money_centavos(cumulative_income)} | "
            f"salidas {self._money_centavos(cumulative_out)} | "
            f"flujo neto {self._money_centavos(cumulative_income - cumulative_out)}"
        )

    def _refresh_general_closing(self) -> None:
        snapshot = self.general_service.get_summary(self._selected_date())
        closed = snapshot["cierre"] is not None
        previous = snapshot["cierre_anterior"] is not None
        for method in self.general_service.METHODS:
            self.general_openings[method].setVisible(
                method != "Efectivo" and not closed and not previous
            )
            self.general_initial_labels[method].setVisible(
                method == "Efectivo" or closed or previous
            )
            self.general_actual[method].setVisible(not closed)
            self.general_real_labels[method].setVisible(closed)
        if closed:
            self.general_notes.setText(snapshot["cierre"]["notas"])
        self.general_notes.setEnabled(not closed)
        self.confirm_general_button.setEnabled(
            not closed and snapshot["cierre_caja_chica"] is not None
        )
        if closed:
            self.general_cut_status.setText(
                f"CORTE GENERAL CONFIRMADO ({snapshot['cierre']['confirmado_en']}). "
                "Los importes están guardados y no son editables."
            )
        elif snapshot["cierre_caja_chica"] is None:
            self.general_cut_status.setText(
                "Primero confirma el corte de efectivo en Caja chica."
            )
        else:
            self.general_cut_status.setText(
                "Corte general pendiente: captura los saldos reales de "
                "los tres medios de pago."
            )
        self._update_general_preview()

    def _update_general_preview(self, *_):
        if not hasattr(self, "general_actual"):
            return
        card = self._optional_amount(self.general_openings["Tarjeta"])
        transfer = self._optional_amount(self.general_openings["Transferencia"])
        snapshot = self.general_service.get_summary(
            self._selected_date(), card, transfer
        )
        for row in snapshot["medios"]:
            method = row["metodo_pago"]
            starting = row["saldo_inicial_centavos"]
            self.general_initial_labels[method].setText(
                self._money_centavos(starting)
            )
            for key in (
                "entradas_centavos", "compras_centavos",
                "otras_salidas_centavos", "saldo_esperado_centavos",
            ):
                self.general_summary_cells[(method, key)].setText(
                    self._money_centavos(row[key])
                )
            if snapshot["cierre"]:
                actual = row["saldo_real_centavos"]
                self.general_real_labels[method].setText(
                    self._money_centavos(actual)
                )
                difference = row["diferencia_centavos"]
            else:
                actual = self._optional_amount(self.general_actual[method])
                difference = (
                    None if actual is None or
                    row["saldo_esperado_centavos"] is None else
                    round(actual * 100) - row["saldo_esperado_centavos"]
                )
            self.general_summary_cells[(method, "diferencia_centavos")].setText(
                self._money_centavos(difference)
            )

    def _confirm_general_closing(self) -> None:
        day = self._selected_date()
        actual = {}
        for method, field in self.general_actual.items():
            amount = self._optional_amount(field)
            if amount is None:
                QMessageBox.warning(
                    self, "Faltan saldos",
                    f"Captura el saldo real de {method}."
                )
                return
            actual[method] = amount
        initial = {
            method: self._optional_amount(field)
            for method, field in self.general_openings.items()
            if method != "Efectivo"
        }
        reply = QMessageBox.question(
            self, "Confirmar corte general",
            f"¿Confirmar el corte general del {day}?\n\n"
            "Quedarán guardados los saldos reales y las diferencias "
            "de efectivo, tarjeta y transferencia. "
            "Este registro no se podrá editar desde esta pantalla.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.general_service.confirm(
                day, actual, initial, self.general_notes.text()
            )
        except (ValueError, OSError) as error:
            QMessageBox.warning(
                self, "No se pudo confirmar el corte general", str(error)
            )
            return
        self._refresh_general_closing()
        QMessageBox.information(
            self, "Corte general confirmado",
            "Se guardaron los saldos y las diferencias de los tres medios."
        )

    def _create_profit_hover_popup(self):
        """El mismo desglose de la antigua sección y costos, en una sola ficha."""
        popup = QFrame(self, Qt.WindowType.ToolTip)
        popup.setObjectName("profitHoverPopup")
        popup.setFrameShape(QFrame.Shape.StyledPanel)
        popup.setAutoFillBackground(True)
        popup.setMinimumWidth(760)
        popup.resize(850, 450)
        popup.installEventFilter(self)
        main = QVBoxLayout(popup)
        heading = QLabel("Cómo se calcula la utilidad del día")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        main.addWidget(heading)
        grid = QGridLayout()
        self.profit_values = {}
        for index, (key, label) in enumerate((
            ("dinero_neto", "Ingresos netos por ventas"),
            ("costo", "(-) Costo de mercancía vendida"),
            ("utilidad_bruta", "(=) Utilidad bruta después de comisiones"),
            ("gastos_fijos", "(-) Gastos Fijos"),
            ("gastos_variables", "(-) Gastos variables"),
            ("gastos_operativos", "(-) Total gastos operativos"),
            ("utilidad_operativa", "(=) Utilidad operativa"),
            ("sobre_valores", "Sobre/Valores: salida de efectivo, no gasto"),
        )):
            row, col = divmod(index, 2)
            container = QVBoxLayout()
            container.addWidget(QLabel(label))
            value = QLabel("$ 0.00")
            value.setStyleSheet("font-size: 16px; font-weight: bold;")
            container.addWidget(value)
            self.profit_values[key] = value
            grid.addLayout(container, row, col)
        main.addLayout(grid)
        main.addWidget(QLabel(
            "Costo de mercancía vendida por producto "
            "(costo histórico de cada venta):"
        ))
        self.profit_cost_table = QTableWidget(0, 5)
        self.profit_cost_table.setObjectName("hover_cost_details")
        self.profit_cost_table.setHorizontalHeaderLabels((
            "Código", "Producto", "Cantidad vendida", "Costo unitario",
            "Costo de mercancía vendida",
        ))
        self.profit_cost_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.profit_cost_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.profit_cost_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.profit_cost_table.setMinimumHeight(165)
        main.addWidget(self.profit_cost_table)
        explanation = QLabel(
            "La compra de inventario no reduce dos veces la utilidad. "
            "Los traspasos Sobre/Valores tampoco son gastos operativos."
        )
        explanation.setWordWrap(True)
        main.addWidget(explanation)
        self._profit_popup = popup

    def _populate_profit_hover(self):
        data = self.service.get_daily_closing(self._selected_date())
        for key, widget in self.profit_values.items():
            widget.setText(f"$ {data[key]:,.2f}")
        costs = self.service.get_sold_cost_breakdown(self._selected_date())
        self.profit_cost_table.setRowCount(len(costs))
        for row, item in enumerate(costs):
            values = (
                item["codigo"], item["producto"],
                f'{item["cantidad"]:g}',
                f'$ {item["costo_unitario"]:,.2f}',
                f'$ {item["costo_total"]:,.2f}',
            )
            for column, value in enumerate(values):
                self.profit_cost_table.setItem(
                    row, column, QTableWidgetItem(str(value))
                )

    def _show_profit_popup(self, anchor=None):
        if not self._profit_popup:
            return
        anchor = anchor or self._profit_hover_targets[-1]
        self._populate_profit_hover()
        self._profit_popup.adjustSize()
        wanted = anchor.mapToGlobal(anchor.rect().bottomLeft())
        screen = QApplication.screenAt(wanted) or QApplication.primaryScreen()
        if screen:
            bounds = screen.availableGeometry()
            x = min(max(wanted.x(), bounds.left()), max(
                bounds.left(), bounds.right() - self._profit_popup.width()
            ))
            y = wanted.y() + 5
            if y + self._profit_popup.height() > bounds.bottom():
                y = max(bounds.top(), anchor.mapToGlobal(
                    anchor.rect().topLeft()
                ).y() - self._profit_popup.height() - 5)
            self._profit_popup.move(x, y)
        else:
            self._profit_popup.move(wanted)
        self._profit_popup.show()

    def _maybe_hide_profit_popup(self):
        if not self._profit_popup or not self._profit_popup.isVisible():
            return
        point = QCursor.pos()
        popup_local = self._profit_popup.mapFromGlobal(point)
        if self._profit_popup.rect().contains(popup_local):
            return
        for target in self._profit_hover_targets:
            local = target.mapFromGlobal(point)
            if target.rect().contains(local):
                return
        self._profit_popup.hide()

    def eventFilter(self, watched, event):
        if not hasattr(self, "_profit_hover_targets"):
            return super().eventFilter(watched, event)
        if watched in self._profit_hover_targets:
            if event.type() == QEvent.Type.Enter:
                self._show_profit_popup(watched)
            elif event.type() == QEvent.Type.Leave:
                QTimer.singleShot(230, self._maybe_hide_profit_popup)
        elif watched is self._profit_popup and event.type() == QEvent.Type.Leave:
            QTimer.singleShot(230, self._maybe_hide_profit_popup)
        return super().eventFilter(watched, event)

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
        for field in (*self.general_openings.values(), *self.general_actual.values()):
            field.clear()
        self.general_notes.clear()
        if self._profit_popup and self._profit_popup.isVisible():
            self._profit_popup.hide()
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
        for key, widget in self.profit_values.items():
            widget.setText(f"$ {data[key]:,.2f}")
        self.values["numero_tickets"].setText(str(data["numero_tickets"]))
        self.values["productos_vendidos"].setText(
            f"{data['productos_vendidos']:g}"
        )
        self._refresh_petty_cash()
        self._refresh_concept_movements()
        self._refresh_general_closing()
        self._update_cash_reconciliation()

    def _build_cost_breakdown_dialog(self) -> QDialog:
        """Desglose verificable del costo histórico de los productos vendidos."""
        day = self._selected_date()
        data = self.service.get_daily_closing(day)
        items = self.service.get_sold_cost_breakdown(day)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Costo de mercancía vendida - {day}")
        dialog.resize(830, 510)
        layout = QVBoxLayout(dialog)
        title = QLabel(f"Desglose de utilidad y costos - {day}")
        title.setStyleSheet("font-size: 19px; font-weight: bold;")
        layout.addWidget(title)
        layout.addWidget(QLabel(
            "Los costos son los registrados al momento de cada venta, "
            "no los importes desembolsados en compras del día."
        ))
        table = QTableWidget(len(items), 5)
        table.setObjectName("cost_detail")
        table.setHorizontalHeaderLabels((
            "Código", "Producto", "Cantidad vendida",
            "Costo unitario en venta", "Costo total",
        ))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        for row, item in enumerate(items):
            values = (
                item["codigo"], item["producto"],
                f'{item["cantidad"]:g}',
                f'$ {item["costo_unitario"]:,.2f}',
                f'$ {item["costo_total"]:,.2f}',
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(str(value)))
        layout.addWidget(table)
        summary = QLabel(
            f"Ingreso neto por ventas: $ {data['dinero_neto']:,.2f}\n"
            f"(-) Costo vendido: $ {data['costo']:,.2f}\n"
            f"(=) Utilidad bruta: $ {data['utilidad_bruta']:,.2f}\n"
            f"(-) Gastos fijos: $ {data['gastos_fijos']:,.2f}\n"
            f"(-) Gastos variables: $ {data['gastos_variables']:,.2f}\n"
            f"(=) Utilidad operativa estimada: $ {data['utilidad']:,.2f}"
        )
        summary.setObjectName("cost_profit_summary")
        layout.addWidget(summary)
        close = QPushButton("Cerrar")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        return dialog

    def _show_cost_breakdown(self) -> None:
        self._build_cost_breakdown_dialog().exec()

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
        self.cash_purchases.setText(
            f"$ {summary['compras_efectivo_centavos'] / 100:,.2f}"
        )
        for row, flow in enumerate(
            self.petty_cash.get_payment_flows(self._selected_date())
        ):
            for column, value in enumerate((
                flow["metodo_pago"],
                f"$ {flow['entradas_centavos'] / 100:,.2f}",
                f"$ {flow['compras_centavos'] / 100:,.2f}",
                f"$ {flow['flujo_neto_centavos'] / 100:,.2f}",
            )):
                cell = QTableWidgetItem(str(value))
                if column:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                self.payment_flows.setItem(row, column, cell)
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
        self._update_cash_reconciliation()
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
        closing = self.petty_cash.get_closing(self._selected_date())
        if closing:
            # Los campos se mantienen vacíos/solo lectura en fechas cerradas.
            # Mostrar el corte guardado, no el "cero" del formulario vacío.
            self.cash_expected.setText(
                f"$ {closing['saldo_esperado_centavos'] / 100:,.2f}"
            )
            self.cash_counted.setText(
                f"$ {closing['saldo_contado_centavos'] / 100:,.2f}"
            )
            self.cash_difference.setText("$ 0.00")
            self.cash_status.setText("CONFIRMADO")
            self._cash_is_balanced = True
        else:
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
