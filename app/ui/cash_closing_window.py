from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import Database
from app.services.cash_closing_service import CashClosingService


class CashClosingWindow(QWidget):
    """Resumen y exportación del corte diario."""

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.service = CashClosingService(database)
        self._create_ui()
        self.refresh()

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 25)
        layout.setSpacing(14)

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
        cash_layout.addWidget(QLabel("Tipo"), 0, 5)
        cash_layout.addWidget(QLabel("Denominación"), 0, 6)
        cash_layout.addWidget(QLabel("Cantidad"), 0, 7)
        cash_layout.addWidget(QLabel("Importe"), 0, 8)
        self.cash_inputs = {}
        self.cash_amounts = {}
        bills = [row for row in self.service.DENOMINATIONS if row[0] == "Billete"]
        coins = [row for row in self.service.DENOMINATIONS if row[0] == "Moneda"]
        for side, denominations in enumerate((bills, coins)):
            base_column = 0 if side == 0 else 5
            for row, (kind, denomination) in enumerate(denominations, start=1):
                cash_layout.addWidget(QLabel(kind), row, base_column)
                cash_layout.addWidget(
                    QLabel(f"$ {denomination:,.2f}"), row, base_column + 1
                )
                quantity = QSpinBox()
                quantity.setRange(0, 9999)
                quantity.valueChanged.connect(self._update_cash_reconciliation)
                cash_layout.addWidget(quantity, row, base_column + 2)
                amount = QLabel("$ 0.00")
                amount.setAlignment(Qt.AlignmentFlag.AlignRight)
                cash_layout.addWidget(amount, row, base_column + 3)
                key = (kind, denomination)
                self.cash_inputs[key] = quantity
                self.cash_amounts[key] = amount

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
        layout.addStretch()

    def _selected_date(self) -> str:
        return self.date.date().toString("yyyy-MM-dd")

    def _date_changed(self) -> None:
        for widget in self.cash_inputs.values():
            widget.blockSignals(True)
            widget.setValue(0)
            widget.blockSignals(False)
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
        self._update_cash_reconciliation()

    def _cash_counts(self) -> dict[tuple[str, float], int]:
        return {
            key: widget.value()
            for key, widget in self.cash_inputs.items()
        }

    def _update_cash_reconciliation(self) -> None:
        cash = self.service.calculate_cash_reconciliation(
            self._selected_date(), self._cash_counts()
        )
        for row in cash["denominaciones"]:
            key = (row["tipo"], row["denominacion"])
            self.cash_amounts[key].setText(f"$ {row['importe']:,.2f}")
        self.cash_expected.setText(f"$ {cash['efectivo_esperado']:,.2f}")
        self.cash_counted.setText(f"$ {cash['efectivo_contado']:,.2f}")
        self.cash_difference.setText(f"$ {cash['diferencia']:,.2f}")
        self.cash_status.setText(cash["estado"])
        color = "#1B5E20" if cash["estado"] == "CUADRA" else "#B71C1C"
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
            output_path = exporter(date, destination, self._cash_counts())
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "No se pudo exportar", str(error))
            return
        QMessageBox.information(
            self, "Corte exportado",
            f"El corte se guardó correctamente en:\n{output_path}",
        )
