from datetime import datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import Database
from app.services.purchase_service import PurchaseService


class PurchaseDetailDialog(QDialog):
    """Muestra los productos incluidos en una compra."""

    def __init__(self, purchase: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Compra {purchase['folio']}")
        self.resize(850, 500)

        layout = QVBoxLayout(self)
        title = QLabel(f"Compra {purchase['folio']}")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        layout.addWidget(
            QLabel(
                f"Fecha: {purchase['fecha']}\n"
                f"Proveedor: {purchase['proveedor']}\n"
                f"Notas: {purchase['notas'] or 'Sin notas'}"
            )
        )

        table = QTableWidget(len(purchase["items"]), 5)
        table.setHorizontalHeaderLabels(
            ["Código", "Producto", "Cantidad", "Costo unitario", "Importe"]
        )
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        for row, item in enumerate(purchase["items"]):
            values = (
                item["codigo"], item["nombre"], f"{item['cantidad']:g}",
                f"$ {item['costo_unitario']:,.2f}",
                f"$ {item['subtotal']:,.2f}",
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(str(value)))

        layout.addWidget(table)
        total = QLabel(f"Total: $ {purchase['total']:,.2f}")
        total.setAlignment(Qt.AlignmentFlag.AlignRight)
        total.setStyleSheet("font-size: 17px; font-weight: bold;")
        layout.addWidget(total)

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)


class PurchaseHistoryWindow(QWidget):
    """Consulta y exportación del historial de compras."""

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.database = database
        self.service = PurchaseService(database)
        self.purchases: list[dict] = []
        self._create_ui()
        self.refresh()

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 25)
        layout.setSpacing(12)

        title = QLabel("Historial de Compras")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(title)

        search_layout = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Buscar por folio, proveedor o notas..."
        )
        self.search.returnPressed.connect(self._load_purchases)
        search_layout.addWidget(self.search, 1)

        search_button = QPushButton("Buscar")
        search_button.clicked.connect(self._load_purchases)
        search_layout.addWidget(search_button)

        search_layout.addWidget(QLabel("Proveedor:"))
        self.supplier = QComboBox()
        self.supplier.setMinimumWidth(220)
        self.supplier.currentIndexChanged.connect(self._load_purchases)
        search_layout.addWidget(self.supplier)
        layout.addLayout(search_layout)

        period_layout = QHBoxLayout()
        self.filter_dates = QCheckBox("Filtrar por fechas")
        self.filter_dates.stateChanged.connect(self._update_date_filter)
        period_layout.addWidget(self.filter_dates)

        period_layout.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setDate(QDate(datetime.now().year, 1, 1))
        self.date_from.dateChanged.connect(self._load_purchases)
        period_layout.addWidget(self.date_from)

        period_layout.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self._load_purchases)
        period_layout.addWidget(self.date_to)
        period_layout.addStretch()
        layout.addLayout(period_layout)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Folio", "Fecha", "Proveedor", "Subtotal", "Total", "Notas"]
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._show_detail)
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        export_button = QPushButton("Exportar Excel")
        export_button.setMinimumSize(140, 40)
        export_button.clicked.connect(self._export_excel)
        buttons.addWidget(export_button)
        detail_button = QPushButton("Ver detalle")
        detail_button.setMinimumSize(130, 40)
        detail_button.clicked.connect(self._show_detail)
        buttons.addWidget(detail_button)
        layout.addLayout(buttons)

        self._load_suppliers()
        self._update_date_filter()

    def _load_suppliers(self) -> None:
        current = self.supplier.currentData()
        self.supplier.blockSignals(True)
        self.supplier.clear()
        self.supplier.addItem("Todos los proveedores", None)

        cursor = self.database.cursor()
        cursor.execute(
            "SELECT id, nombre FROM proveedores WHERE activo = 1 ORDER BY nombre"
        )
        for row in cursor.fetchall():
            self.supplier.addItem(row["nombre"], row["id"])

        index = self.supplier.findData(current)
        self.supplier.setCurrentIndex(max(index, 0))
        self.supplier.blockSignals(False)

    def _active_period(self) -> tuple[str | None, str | None]:
        if not self.filter_dates.isChecked():
            return None, None
        return (
            self.date_from.date().toString("yyyy-MM-dd"),
            self.date_to.date().toString("yyyy-MM-dd"),
        )

    def _update_date_filter(self) -> None:
        enabled = self.filter_dates.isChecked()
        self.date_from.setEnabled(enabled)
        self.date_to.setEnabled(enabled)
        if hasattr(self, "table"):
            self._load_purchases()

    def _load_purchases(self) -> None:
        date_from, date_to = self._active_period()
        self.purchases = self.service.list_purchases(
            search=self.search.text(),
            supplier_id=self.supplier.currentData(),
            date_from=date_from,
            date_to=date_to,
        )

        self.table.setRowCount(0)
        for row, purchase in enumerate(self.purchases):
            self.table.insertRow(row)
            values = (
                purchase["folio"], purchase["fecha"], purchase["proveedor"],
                f"$ {purchase['subtotal']:,.2f}",
                f"$ {purchase['total']:,.2f}", purchase["notas"] or "",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))

    def _show_detail(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.purchases):
            QMessageBox.information(
                self, "Selecciona una compra", "Selecciona una compra."
            )
            return

        purchase = self.service.get_purchase(self.purchases[row]["id"])
        if purchase is None:
            QMessageBox.warning(
                self, "Compra no encontrada", "La compra ya no está disponible."
            )
            self._load_purchases()
            return

        PurchaseDetailDialog(purchase, self).exec()

    def _export_excel(self) -> None:
        date_from, date_to = self._active_period()
        if date_from and date_to and date_from > date_to:
            QMessageBox.warning(
                self,
                "Periodo no válido",
                "La fecha inicial no puede ser posterior a la fecha final.",
            )
            return

        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar historial de compras",
            "historial_compras.xlsx",
            "Archivos de Excel (*.xlsx)",
        )
        if not destination:
            return

        try:
            output_path = self.service.export_purchases_report(
                destination=destination,
                search=self.search.text(),
                supplier_id=self.supplier.currentData(),
                date_from=date_from,
                date_to=date_to,
            )
        except (OSError, PermissionError, ValueError) as error:
            QMessageBox.critical(
                self,
                "No se pudo exportar",
                f"No fue posible crear el reporte:\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "Reporte exportado",
            f"El reporte se guardó correctamente en:\n{output_path}",
        )

    def refresh(self) -> None:
        self._load_suppliers()
        self._load_purchases()
