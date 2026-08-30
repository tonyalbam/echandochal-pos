from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
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
            5,
        )

        tabla.setHorizontalHeaderLabels(
            [
                "Código",
                "Producto",
                "Cantidad",
                "Precio",
                "Importe",
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
        self.sales = self.service.list_sales(
            search=self.buscar.text(),
            include_cancelled=(
                self.mostrar_canceladas.isChecked()
            ),
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

    def _actualizar_botones(self) -> None:
        """Actualiza el estado de los botones según la venta seleccionada."""

        fila = self.tabla.currentRow()

        if fila < 0 or fila >= len(self.sales):
            self.detalle.setEnabled(False)
            self.cancelar.setEnabled(False)
            return

        sale = self.sales[fila]

        self.detalle.setEnabled(True)

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