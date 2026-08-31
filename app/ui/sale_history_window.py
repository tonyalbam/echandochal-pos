from datetime import datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
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
from app.services.sale_history_service import SaleHistoryService
from app.services.ticket_service import TicketService


class SaleDetailDialog(QDialog):
    """Muestra el detalle de una venta."""

    def __init__(
        self,
        sale: dict,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle(
            f"Venta {sale['folio']}"
        )

        self.resize(850, 500)

        layout = QVBoxLayout(self)

        titulo = QLabel(
            f"Venta {sale['folio']}"
        )

        titulo.setStyleSheet(
            "font-size: 24px; font-weight: bold;"
        )

        layout.addWidget(titulo)

        estado = (
            "CANCELADA"
            if sale["cancelada"]
            else "ACTIVA"
        )

        informacion = QLabel(
            f"Fecha: {sale['fecha']}  "
            f"Hora: {sale['hora']}\n"
            f"Forma de pago: {sale['metodo_pago']}\n"
            f"Estado: {estado}"
        )

        if sale["cancelada"]:
            informacion.setStyleSheet(
                "font-weight: bold;"
            )

        layout.addWidget(informacion)

        tabla = QTableWidget(
            len(sale["items"]),
            7,
        )

        tabla.setHorizontalHeaderLabels(
            [
                "Código",
                "Producto",
                "Cantidad",
                "Precio",
                "Importe",
                "Forma de pago",
                "Comisión",
            ]
        )

        tabla.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )

        tabla.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        for row, item in enumerate(
            sale["items"]
        ):
            tabla.setItem(
                row,
                0,
                QTableWidgetItem(
                    item["codigo"]
                ),
            )

            tabla.setItem(
                row,
                1,
                QTableWidgetItem(
                    item["nombre"]
                ),
            )

            tabla.setItem(
                row,
                2,
                QTableWidgetItem(
                    f"{item['cantidad']:g}"
                ),
            )

            tabla.setItem(
                row,
                3,
                QTableWidgetItem(
                    f"$ {item['precio_unitario']:,.2f}"
                ),
            )

            tabla.setItem(
                row,
                4,
                QTableWidgetItem(
                    f"$ {item['subtotal']:,.2f}"
                ),
            )

            tabla.setItem(
                row, 5, QTableWidgetItem(item["metodo_pago"])
            )
            tabla.setItem(
                row, 6,
                QTableWidgetItem(f"$ {item['monto_comision']:,.2f}"),
            )

        layout.addWidget(tabla)

        resumen = QLabel(
            f"Subtotal: $ {sale['subtotal']:,.2f}\n"
            f"Descuento: $ {sale['descuento']:,.2f}\n"
            f"Total: $ {sale['total']:,.2f}\n"
            f"Comisión: $ {sale['monto_comision']:,.2f}\n"
            f"Neto: $ {sale['total_neto']:,.2f}"
        )

        resumen.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        resumen.setStyleSheet(
            "font-size: 15px;"
        )

        layout.addWidget(resumen)

        cerrar = QPushButton("Cerrar")

        cerrar.clicked.connect(
            self.accept
        )

        layout.addWidget(
            cerrar,
            alignment=Qt.AlignmentFlag.AlignRight,
        )


class SaleHistoryWindow(QWidget):
    """Historial de ventas de Echando Chal POS."""

    def __init__(
        self,
        database: Database,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.database = database

        self.service = SaleHistoryService(
            database
        )
        self.ticket_service = TicketService(database)

        self.sales: list[dict] = []

        self._crear_interfaz()
        self._load_sales()

    def _crear_interfaz(self) -> None:
        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            25,
            20,
            25,
            25,
        )

        layout.setSpacing(12)

        titulo = QLabel(
            "Historial de Ventas"
        )

        titulo.setStyleSheet(
            "font-size: 28px; font-weight: bold;"
        )

        layout.addWidget(titulo)

        controles = QHBoxLayout()

        self.buscar = QLineEdit()

        self.buscar.setPlaceholderText(
            "Buscar por folio o forma de pago..."
        )

        self.buscar.returnPressed.connect(
            self._load_sales
        )

        controles.addWidget(
            self.buscar,
            1,
        )

        buscar = QPushButton("Buscar")

        buscar.clicked.connect(
            self._load_sales
        )

        controles.addWidget(
            buscar
        )

        self.mostrar_canceladas = QCheckBox(
            "Mostrar canceladas"
        )

        self.mostrar_canceladas.setChecked(
            True
        )

        self.mostrar_canceladas.stateChanged.connect(
            self._load_sales
        )

        controles.addWidget(
            self.mostrar_canceladas
        )

        layout.addLayout(controles)

        periodo = QHBoxLayout()

        self.filtrar_fechas = QCheckBox("Filtrar por fechas")
        self.filtrar_fechas.stateChanged.connect(
            self._actualizar_filtro_fechas
        )
        periodo.addWidget(self.filtrar_fechas)

        periodo.addWidget(QLabel("Desde:"))
        self.fecha_desde = QDateEdit()
        self.fecha_desde.setCalendarPopup(True)
        self.fecha_desde.setDisplayFormat("yyyy-MM-dd")
        self.fecha_desde.setDate(QDate(datetime.now().year, 1, 1))
        self.fecha_desde.dateChanged.connect(self._load_sales)
        periodo.addWidget(self.fecha_desde)

        periodo.addWidget(QLabel("Hasta:"))
        self.fecha_hasta = QDateEdit()
        self.fecha_hasta.setCalendarPopup(True)
        self.fecha_hasta.setDisplayFormat("yyyy-MM-dd")
        self.fecha_hasta.setDate(QDate.currentDate())
        self.fecha_hasta.dateChanged.connect(self._load_sales)
        periodo.addWidget(self.fecha_hasta)
        periodo.addStretch()

        layout.addLayout(periodo)
        self._actualizar_filtro_fechas()

        self.tabla = QTableWidget(
            0,
            9,
        )

        self.tabla.setHorizontalHeaderLabels(
            [
                "Folio",
                "Fecha",
                "Hora",
                "Forma de pago",
                "Subtotal",
                "Descuento",
                "Total",
                "Comisión",
                "Estado",
            ]
        )

        self.tabla.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.tabla.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )

        self.tabla.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.tabla.doubleClicked.connect(
            self._mostrar_detalle
        )

        self.tabla.itemSelectionChanged.connect(
            self._actualizar_botones
        )

        header = self.tabla.horizontalHeader()

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            8,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        layout.addWidget(
            self.tabla,
            1,
        )

        botones = QHBoxLayout()

        botones.addStretch()

        self.exportar = QPushButton("Exportar Excel")
        self.exportar.setMinimumSize(140, 40)
        self.exportar.clicked.connect(self._exportar_excel)
        botones.addWidget(self.exportar)

        self.ticket = QPushButton("Ticket PDF")
        self.ticket.setMinimumSize(120, 40)
        self.ticket.clicked.connect(self._exportar_ticket)
        botones.addWidget(self.ticket)

        self.detalle = QPushButton(
            "Ver detalle"
        )

        self.detalle.setMinimumSize(
            130,
            40,
        )

        self.detalle.clicked.connect(
            self._mostrar_detalle
        )

        botones.addWidget(
            self.detalle
        )

        self.cancelar = QPushButton(
            "Cancelar venta"
        )

        self.cancelar.setMinimumSize(
            150,
            40,
        )

        self.cancelar.clicked.connect(
            self._cancelar_venta
        )

        botones.addWidget(
            self.cancelar
        )

        layout.addLayout(botones)

        self._actualizar_botones()

    def _load_sales(self) -> None:
        date_from, date_to = self._periodo_activo()

        self.sales = self.service.list_sales(
            search=self.buscar.text(),
            include_cancelled=(
                self.mostrar_canceladas.isChecked()
            ),
            date_from=date_from,
            date_to=date_to,
        )

        self.tabla.setRowCount(0)

        for row, sale in enumerate(
            self.sales
        ):
            self.tabla.insertRow(row)

            valores = [
                sale["folio"],
                sale["fecha"],
                sale["hora"],
                sale["metodo_pago"],
                f"$ {sale['subtotal']:,.2f}",
                f"$ {sale['descuento']:,.2f}",
                f"$ {sale['total']:,.2f}",
                f"$ {sale['monto_comision']:,.2f}",
                (
                    "CANCELADA"
                    if sale["cancelada"]
                    else "ACTIVA"
                ),
            ]

            for column, value in enumerate(
                valores
            ):
                item = QTableWidgetItem(
                    str(value)
                )

                self.tabla.setItem(
                    row,
                    column,
                    item,
                )

        self._actualizar_botones()

    def _periodo_activo(self) -> tuple[str | None, str | None]:
        if not self.filtrar_fechas.isChecked():
            return None, None

        return (
            self.fecha_desde.date().toString("yyyy-MM-dd"),
            self.fecha_hasta.date().toString("yyyy-MM-dd"),
        )

    def _actualizar_filtro_fechas(self) -> None:
        enabled = self.filtrar_fechas.isChecked()
        self.fecha_desde.setEnabled(enabled)
        self.fecha_hasta.setEnabled(enabled)

        if hasattr(self, "tabla"):
            self._load_sales()

    def _exportar_excel(self) -> None:
        date_from, date_to = self._periodo_activo()

        if date_from and date_to and date_from > date_to:
            QMessageBox.warning(
                self,
                "Periodo no válido",
                "La fecha inicial no puede ser posterior a la fecha final.",
            )
            return

        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar detalle de ventas",
            "detalle_ventas.xlsx",
            "Archivos de Excel (*.xlsx)",
        )
        if not destination:
            return

        try:
            output_path = self.service.export_sales_report(
                destination=destination,
                search=self.buscar.text(),
                include_cancelled=self.mostrar_canceladas.isChecked(),
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

    def _actualizar_botones(self) -> None:
        """Actualiza el estado de los botones según la venta seleccionada."""

        fila = self.tabla.currentRow()

        if fila < 0 or fila >= len(self.sales):
            self.detalle.setEnabled(False)
            self.ticket.setEnabled(False)
            self.cancelar.setEnabled(False)
            return

        sale = self.sales[fila]

        self.detalle.setEnabled(True)
        self.ticket.setEnabled(True)

        self.cancelar.setEnabled(
            not bool(sale["cancelada"])
        )

    def _mostrar_detalle(self) -> None:
        fila = self.tabla.currentRow()

        if fila < 0:
            QMessageBox.information(
                self,
                "Selecciona una venta",
                "Selecciona una venta para ver su detalle.",
            )

            return

        sale = self.sales[fila]

        detalle = self.service.get_sale(
            sale["id"]
        )

        if detalle is None:
            QMessageBox.warning(
                self,
                "Venta no encontrada",
                "La venta ya no está disponible.",
            )

            self._load_sales()

            return

        dialogo = SaleDetailDialog(
            detalle,
            self,
        )

        dialogo.exec()

    def _exportar_ticket(self) -> None:
        fila = self.tabla.currentRow()
        if fila < 0 or fila >= len(self.sales):
            QMessageBox.information(
                self,
                "Selecciona una venta",
                "Selecciona una venta para generar su ticket.",
            )
            return

        sale = self.sales[fila]
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar ticket de venta",
            f"ticket_{sale['folio']}.pdf",
            "Documento PDF (*.pdf)",
        )
        if not destination:
            return

        try:
            output_path = self.ticket_service.generate_sale_ticket(
                sale["id"],
                destination,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "No se pudo crear el ticket",
                str(error),
            )
            return

        QMessageBox.information(
            self,
            "Ticket guardado",
            f"El ticket se guardó correctamente en:\n{output_path}",
        )

    def _cancelar_venta(self) -> None:
        fila = self.tabla.currentRow()

        if fila < 0 or fila >= len(self.sales):
            QMessageBox.information(
                self,
                "Selecciona una venta",
                "Selecciona una venta para cancelar.",
            )

            return

        sale = self.sales[fila]

        if sale["cancelada"]:
            QMessageBox.information(
                self,
                "Venta ya cancelada",
                "La venta seleccionada ya está cancelada.",
            )

            return

        folio = sale["folio"]

        respuesta = QMessageBox.question(
            self,
            "Cancelar venta",
            (
                f"¿Estás seguro de que deseas cancelar "
                f"la venta {folio}?\n\n"
                "Esta operación devolverá los productos "
                "al inventario."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            resultado = self.service.cancel_sale(
                sale["id"]
            )

        except ValueError as error:
            QMessageBox.warning(
                self,
                "No se pudo cancelar",
                str(error),
            )

            self._load_sales()

            return

        except Exception as error:
            QMessageBox.critical(
                self,
                "Error",
                (
                    "Ocurrió un error al cancelar "
                    "la venta.\n\n"
                    f"{error}"
                ),
            )

            self._load_sales()

            return

        QMessageBox.information(
            self,
            "Venta cancelada",
            (
                "La venta se canceló correctamente.\n\n"
                f"Folio: {resultado['folio']}\n"
                f"Productos devueltos: "
                f"{resultado['productos_devueltos']}"
            ),
        )

        self._load_sales()

    def refresh(self) -> None:
        self._load_sales()
