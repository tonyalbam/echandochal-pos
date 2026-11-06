"""Historial de cierres de efectivo y movimientos de caja chica."""
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.services.cash_closing_history_service import CashClosingHistoryService


MONTHS = (
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)


def money(cents):
    return "Pendiente" if cents is None else f"$ {cents / 100:,.2f}"


class CashClosingHistoryWindow(QWidget):
    """Consulta de solo lectura con agrupación por año y mes."""

    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.service = CashClosingHistoryService(database)
        self._items_by_date = {}
        self._create_ui()
        self.refresh()

    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 25)
        layout.setSpacing(12)

        heading = QLabel("Historial cortes diarios efectivo")
        heading.setStyleSheet("font-size: 27px; font-weight: bold;")
        layout.addWidget(heading)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Año:"))
        self.year = QComboBox()
        self.year.setMinimumWidth(120)
        self.year.currentIndexChanged.connect(self._filters_changed)
        controls.addWidget(self.year)

        controls.addWidget(QLabel("Mes:"))
        self.month = QComboBox()
        self.month.addItem("Todos los meses", None)
        for month in range(1, 13):
            self.month.addItem(MONTHS[month], month)
        self.month.currentIndexChanged.connect(self._filters_changed)
        controls.addWidget(self.month)

        controls.addWidget(QLabel("Agrupar:"))
        self.grouping = QComboBox()
        self.grouping.addItems(("Año y mes", "Año", "Sin agrupar"))
        self.grouping.currentIndexChanged.connect(self._load_history)
        controls.addWidget(self.grouping)

        reload_button = QPushButton("Actualizar")
        reload_button.clicked.connect(self.refresh)
        controls.addWidget(reload_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.totals = QLabel()
        self.totals.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.totals.setWordWrap(True)
        layout.addWidget(self.totals)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.history = QTreeWidget()
        self.history.setColumnCount(7)
        self.history.setHeaderLabels((
            "Periodo / Fecha", "Días", "Entradas efectivo",
            "Gastos", "Saldo inicial", "Saldo final / Contado", "Estado",
        ))
        self.history.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for column in range(1, 7):
            self.history.header().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.history.setAlternatingRowColors(True)
        self.history.itemSelectionChanged.connect(self._show_selected_day)
        splitter.addWidget(self.history)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 6, 0, 0)
        self.day_label = QLabel("Selecciona una fecha para consultar el corte y los gastos.")
        self.day_label.setStyleSheet("font-size: 17px; font-weight: bold;")
        detail_layout.addWidget(self.day_label)

        values_group = QGroupBox("Control de caja chica y confirmación del corte")
        grid = QGridLayout(values_group)
        self.fields = {}
        field_names = (
            ("saldo_inicial_centavos", "Saldo inicial"),
            ("ventas_efectivo_centavos", "Ventas en efectivo (cambio descontado)"),
            ("gastos_centavos", "Gastos operativos"),
            ("saldo_esperado_centavos", "Efectivo esperado"),
            ("saldo_contado_centavos", "Efectivo contado"),
        )
        for index, (key, label) in enumerate(field_names):
            position, col = divmod(index, 3)
            grid.addWidget(QLabel(label), position * 2, col)
            value = QLabel("$ 0.00")
            value.setStyleSheet("font-size: 16px; font-weight: bold;")
            grid.addWidget(value, position * 2 + 1, col)
            self.fields[key] = value
        self.confirmation = QLabel("Sin corte seleccionado")
        grid.addWidget(self.confirmation, 4, 0, 1, 3)
        detail_layout.addWidget(values_group)

        expenses_group = QGroupBox("Histórico de gastos operativos de caja chica")
        expenses_layout = QVBoxLayout(expenses_group)
        self.expenses = QTableWidget(0, 5)
        self.expenses.setHorizontalHeaderLabels((
            "Tipo", "Descripción", "Monto", "Estado", "Registrado",
        ))
        self.expenses.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.expenses.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.expenses.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.expenses.setAlternatingRowColors(True)
        expenses_layout.addWidget(self.expenses)
        detail_layout.addWidget(expenses_group)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        layout.addWidget(splitter, 1)

    def _filters_changed(self, *_):
        self._load_history()

    def refresh(self):
        selected_year = self.year.currentData()
        years = self.service.list_years()
        self.year.blockSignals(True)
        self.year.clear()
        self.year.addItem("Todos los años", None)
        for year in years:
            self.year.addItem(str(year), year)
        match = self.year.findData(selected_year)
        self.year.setCurrentIndex(match if match >= 0 else 0)
        self.year.blockSignals(False)
        self._load_history()

    def _append_row(self, parent, label, record, *, group=False):
        if group:
            summary = self.service.summarize(record)
            values = (
                label, str(summary["dias"]),
                money(summary["ventas_efectivo_centavos"]),
                money(summary["gastos_centavos"]),
                money(summary["saldo_inicial_centavos"]),
                money(summary["saldo_final_centavos"]),
                f"{summary['confirmados']} confirmados",
            )
        else:
            values = (
                label, "1", money(record["ventas_efectivo_centavos"]),
                money(record["gastos_centavos"]),
                money(record["saldo_inicial_centavos"]),
                money(record["saldo_contado_centavos"]),
                "CONFIRMADO" if record["confirmado"] else "PENDIENTE",
            )
        node = QTreeWidgetItem(list(values))
        if parent is None:
            self.history.addTopLevelItem(node)
        else:
            parent.addChild(node)
        if not group:
            node.setData(0, Qt.ItemDataRole.UserRole, record["fecha"])
            self._items_by_date[record["fecha"]] = node
        return node

    def _load_history(self, *_):
        previous = self._selected_date()
        self.history.blockSignals(True)
        self.history.clear()
        self._items_by_date.clear()
        year = self.year.currentData()
        month = self.month.currentData()
        # El filtro mensual obliga a un año explícito. Cuando se elige mes
        # con "Todos los años" se agrupa ese mes de todos los años.
        if year is None and month is not None:
            records = [
                row for row in self.service.list_history()
                if int(row["fecha"][5:7]) == month
            ]
        else:
            records = self.service.list_history(year, month)
        stats = self.service.summarize(records)
        self.totals.setText(
            f"Días registrados: {stats['dias']}  |  "
            f"Cortes confirmados: {stats['confirmados']}  |  "
            f"Entradas en efectivo: {money(stats['ventas_efectivo_centavos'])}  |  "
            f"Gastos de caja chica: {money(stats['gastos_centavos'])}"
        )
        grouping = self.grouping.currentText()
        by_year, by_month = {}, {}
        for record in records:
            day = record["fecha"]
            year_key, month_key = day[:4], day[:7]
            if grouping == "Sin agrupar":
                parent = None
            else:
                if year_key not in by_year:
                    by_year[year_key] = self._append_row(
                        None, year_key,
                        [r for r in records if r["fecha"].startswith(year_key)],
                        group=True,
                    )
                parent = by_year[year_key]
                if grouping == "Año y mes":
                    if month_key not in by_month:
                        by_month[month_key] = self._append_row(
                            parent, f"{MONTHS[int(day[5:7])]} {year_key}",
                            [r for r in records if r["fecha"].startswith(month_key)],
                            group=True,
                        )
                    parent = by_month[month_key]
            self._append_row(parent, day, record)
        self.history.expandAll()
        self.history.blockSignals(False)
        self._clear_detail()
        if previous in self._items_by_date:
            self.history.setCurrentItem(self._items_by_date[previous])
        elif records:
            self.history.setCurrentItem(self._items_by_date[records[0]["fecha"]])

    def _selected_date(self):
        selected = self.history.currentItem()
        if selected is None:
            return None
        return selected.data(0, Qt.ItemDataRole.UserRole)

    def _clear_detail(self):
        self.day_label.setText("Selecciona una fecha para consultar el corte y los gastos.")
        for value in self.fields.values():
            value.setText("$ 0.00")
        self.confirmation.setText("Sin corte seleccionado")
        self.expenses.setRowCount(0)

    def _show_selected_day(self):
        day = self._selected_date()
        if not day:
            self._clear_detail()
            return
        detail = self.service.get_day_detail(day)
        self.day_label.setText(f"Detalle del {day}")
        for key, widget in self.fields.items():
            widget.setText(money(detail[key]))
        closing = detail["cierre"]
        self.confirmation.setText(
            f"CONFIRMADO el {closing['confirmado_en']}"
            if closing else "PENDIENTE de confirmar"
        )
        self.expenses.setRowCount(len(detail["gastos"]))
        for row, expense in enumerate(detail["gastos"]):
            values = (
                expense["tipo"], expense["descripcion"],
                money(expense["monto_centavos"]),
                "ANULADO" if expense["anulado"] else "REGISTRADO",
                expense["creado_en"],
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                self.expenses.setItem(row, column, item)
