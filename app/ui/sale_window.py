from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import (
    QCompleter,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
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
from app.services.sale_service import SaleService
from app.services.ticket_service import TicketService


class SaleWindow(QWidget):
    """Pantalla de captura y cobro de ventas."""

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)

        self.database = database
        self.service = SaleService(database)
        self.ticket_service = TicketService(database)
        self.items: list[dict] = []
        self.last_sale_id: int | None = None
        self.suggestion_products: dict[str, dict] = {}

        self._crear_interfaz()
        self._actualizar_totales()

        self.codigo_input.setFocus()

    def _crear_interfaz(self) -> None:
        layout = QVBoxLayout(self)

        layout.setContentsMargins(25, 20, 25, 25)
        layout.setSpacing(12)

        titulo = QLabel("Nueva Venta")
        titulo.setStyleSheet(
            "font-size: 28px; font-weight: bold;"
        )
        layout.addWidget(titulo)

        ayuda = QLabel(
            "Escanea el código de barras o busca por código, nombre o marca; "
            "selecciona una coincidencia para agregarla."
        )
        ayuda.setStyleSheet("color: #666;")
        layout.addWidget(ayuda)

        entrada_layout = QHBoxLayout()

        self.codigo_input = QLineEdit()
        self.codigo_input.setPlaceholderText(
            "Código, código de barras, nombre o marca"
        )
        self.codigo_input.setMinimumHeight(38)
        self.codigo_input.returnPressed.connect(
            self._agregar_por_codigo
        )
        self.suggestion_model = QStringListModel(self)
        self.completer = QCompleter(self.suggestion_model, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(
            QCompleter.CompletionMode.UnfilteredPopupCompletion
        )
        self.completer.setMaxVisibleItems(12)
        self.completer.activated.connect(self._agregar_sugerencia)
        self.codigo_input.setCompleter(self.completer)
        self.codigo_input.textEdited.connect(self._actualizar_sugerencias)

        boton_agregar = QPushButton("Agregar")
        boton_agregar.setMinimumHeight(38)
        boton_agregar.clicked.connect(
            self._agregar_por_codigo
        )

        entrada_layout.addWidget(
            self.codigo_input,
            1,
        )
        entrada_layout.addWidget(
            boton_agregar
        )

        layout.addLayout(entrada_layout)

        self.tabla = QTableWidget(0, 10)

        self.tabla.setHorizontalHeaderLabels(
            [
                "Código",
                "Producto",
                "Marca",
                "Color",
                "Categoría",
                "Cantidad",
                "Precio",
                "Importe",
                "Forma de pago",
                "",
            ]
        )

        self.tabla.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.tabla.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.tabla.verticalHeader().setVisible(False)

        self.tabla.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )

        self.tabla.horizontalHeader().setSectionResizeMode(
            9,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        layout.addWidget(
            self.tabla,
            1,
        )

        controles = QFrame()
        controles_layout = QHBoxLayout(controles)

        controles_layout.setContentsMargins(
            0,
            5,
            0,
            5,
        )

        self.descuento = QDoubleSpinBox()

        self.descuento.setRange(
            0,
            999999.99,
        )

        self.descuento.setDecimals(2)
        self.descuento.setPrefix("$ ")

        self.descuento.valueChanged.connect(
            self._actualizar_totales
        )

        self.descuento.setMinimumHeight(36)

        controles_layout.addWidget(
            QLabel("Descuento:")
        )

        controles_layout.addWidget(
            self.descuento
        )

        controles_layout.addStretch()

        layout.addWidget(controles)

        resumen = QFrame()

        resumen_layout = QVBoxLayout(
            resumen
        )

        resumen_layout.setContentsMargins(
            10,
            5,
            10,
            5,
        )

        self.subtotal_label = QLabel()
        self.comision_label = QLabel()
        self.total_label = QLabel()
        self.neto_label = QLabel()

        for label in (
            self.subtotal_label,
            self.comision_label,
            self.total_label,
            self.neto_label,
        ):
            label.setAlignment(
                Qt.AlignmentFlag.AlignRight
            )

            resumen_layout.addWidget(label)

        self.total_label.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        self.neto_label.setStyleSheet(
            "font-size: 16px; font-weight: bold;"
        )

        layout.addWidget(resumen)

        botones = QHBoxLayout()

        botones.addStretch()

        self.ticket_button = QPushButton("Guardar último ticket")
        self.ticket_button.setMinimumSize(170, 42)
        self.ticket_button.setEnabled(False)
        self.ticket_button.clicked.connect(self._guardar_ultimo_ticket)

        limpiar = QPushButton("Limpiar")

        limpiar.setMinimumSize(
            120,
            42,
        )

        limpiar.clicked.connect(
            self._limpiar_venta
        )

        cobrar = QPushButton("Cobrar")

        cobrar.setMinimumSize(
            150,
            42,
        )

        cobrar.setDefault(True)

        cobrar.clicked.connect(
            self._cobrar
        )

        botones.addWidget(self.ticket_button)
        botones.addWidget(limpiar)
        botones.addWidget(cobrar)

        layout.addLayout(botones)

    def _agregar_por_codigo(self) -> None:
        codigo = self.codigo_input.text().strip()

        if not codigo:
            return

        producto = self.service.find_product(codigo)
        if not producto:
            matches = self.service.search_products(codigo)
            producto = matches[0] if matches else None

        if not producto:
            QMessageBox.warning(
                self,
                "Producto no encontrado",
                (
                    "No se encontró un producto activo "
                    "con el código:\n"
                    f"{codigo}"
                ),
            )

            self.codigo_input.selectAll()
            self.codigo_input.setFocus()

            return

        self._agregar_producto(producto)

    def _actualizar_sugerencias(self, text: str) -> None:
        products = self.service.search_products(text)
        self.suggestion_products = {}
        labels = []
        for product in products:
            brand = f" | {product['marca']}" if product["marca"] else ""
            label = f"{product['codigo']} | {product['nombre']}{brand}"
            labels.append(label)
            self.suggestion_products[label] = product
        self.suggestion_model.setStringList(labels)
        if labels:
            self.completer.complete()

    def _agregar_sugerencia(self, label: str) -> None:
        product = self.suggestion_products.get(label)
        if product:
            self._agregar_producto(product)

    def _agregar_producto(self, producto: dict) -> None:
        for item in self.items:

            if item["producto_id"] == producto["id"]:

                nueva_cantidad = (
                    float(item["cantidad"]) + 1
                )

                if nueva_cantidad > float(
                    producto["existencia"]
                ):
                    QMessageBox.warning(
                        self,
                        "Existencia insuficiente",
                        (
                            f"Solo hay "
                            f"{producto['existencia']:g} "
                            f"disponibles de "
                            f"'{producto['nombre']}'."
                        ),
                    )

                    self.codigo_input.clear()
                    self.codigo_input.setFocus()

                    return

                item["cantidad"] = nueva_cantidad

                self._refrescar_tabla()

                self.codigo_input.clear()
                self.codigo_input.setFocus()

                return

        self.items.append(
            {
                "producto_id": producto["id"],
                "codigo": producto["codigo"],
                "nombre": producto["nombre"],
                "marca": producto["marca"],
                "color": producto["color"],
                "categoria": producto["categoria"],
                "cantidad": 1.0,
                "precio_unitario": float(
                    producto["precio"]
                ),
                "existencia": float(
                    producto["existencia"]
                ),
                "metodo_pago": "Efectivo",
            }
        )

        self._refrescar_tabla()

        self.codigo_input.clear()
        self.codigo_input.setFocus()

    def _refrescar_tabla(self) -> None:
        self.tabla.setRowCount(0)

        for row, item in enumerate(
            self.items
        ):
            self.tabla.insertRow(row)

            self.tabla.setItem(
                row,
                0,
                QTableWidgetItem(
                    item["codigo"]
                ),
            )

            self.tabla.setItem(
                row,
                1,
                QTableWidgetItem(
                    item["nombre"]
                ),
            )

            self.tabla.setItem(
                row,
                2,
                QTableWidgetItem(item["marca"]),
            )

            self.tabla.setItem(
                row,
                3,
                QTableWidgetItem(item["color"]),
            )

            self.tabla.setItem(
                row,
                4,
                QTableWidgetItem(item["categoria"]),
            )

            self.tabla.setItem(
                row,
                5,
                QTableWidgetItem(
                    f"{item['cantidad']:g}"
                ),
            )

            self.tabla.setItem(
                row,
                6,
                QTableWidgetItem(
                    f"$ {item['precio_unitario']:,.2f}"
                ),
            )

            importe = (
                item["cantidad"]
                * item["precio_unitario"]
            )

            self.tabla.setItem(
                row,
                7,
                QTableWidgetItem(
                    f"$ {importe:,.2f}"
                ),
            )

            payment = QComboBox()
            payment.addItems(SaleService.PAYMENT_METHODS)
            payment.setCurrentText(item["metodo_pago"])
            payment.currentTextChanged.connect(
                lambda method, index=row:
                self._cambiar_metodo_pago(index, method)
            )
            self.tabla.setCellWidget(row, 8, payment)

            quitar = QPushButton("Quitar")

            quitar.clicked.connect(
                lambda checked=False, index=row:
                self._quitar_item(index)
            )

            self.tabla.setCellWidget(
                row,
                9,
                quitar,
            )

        self._actualizar_totales()

    def _cambiar_metodo_pago(self, index: int, method: str) -> None:
        if 0 <= index < len(self.items):
            self.items[index]["metodo_pago"] = method
            self._actualizar_totales()

    def _quitar_item(
        self,
        index: int,
    ) -> None:

        if 0 <= index < len(
            self.items
        ):
            self.items.pop(index)

            self._refrescar_tabla()

            self.codigo_input.setFocus()

    def _calcular_subtotal(
        self,
    ) -> float:

        return sum(
            float(item["cantidad"])
            * float(item["precio_unitario"])
            for item in self.items
        )

    def _actualizar_totales(
        self,
    ) -> None:

        subtotal = (
            self._calcular_subtotal()
        )

        descuento = (
            self.descuento.value()
        )

        total = max(
            0.0,
            subtotal - descuento,
        )

        tasa = self.service.get_commission_rate()
        ml_subtotal = sum(
            item["cantidad"] * item["precio_unitario"]
            for item in self.items
            if item["metodo_pago"] == "Mercado Libre"
        )
        ml_total = (
            total * ml_subtotal / subtotal
            if subtotal > 0 else 0.0
        )
        comision = round(ml_total * tasa / 100, 2)

        neto = total - comision

        self.subtotal_label.setText(
            f"Subtotal:  $ {subtotal:,.2f}"
        )

        if ml_subtotal:
            self.comision_label.setText(
                (
                    "Comisión Mercado Libre "
                    f"({tasa:g}%):  "
                    f"$ {comision:,.2f}"
                )
            )

        else:
            self.comision_label.setText(
                "Comisión:  $ 0.00"
            )

        self.total_label.setText(
            f"TOTAL A COBRAR:  $ {total:,.2f}"
        )

        self.neto_label.setText(
            (
                "Neto para Echando Chal:  "
                f"$ {neto:,.2f}"
            )
        )

    def _cobrar(self) -> None:

        if not self.items:
            QMessageBox.warning(
                self,
                "Venta vacía",
                (
                    "Agrega al menos un producto "
                    "antes de cobrar."
                ),
            )

            self.codigo_input.setFocus()

            return

        subtotal = (
            self._calcular_subtotal()
        )

        descuento = (
            self.descuento.value()
        )

        if descuento > subtotal:
            QMessageBox.warning(
                self,
                "Descuento inválido",
                (
                    "El descuento no puede "
                    "superar el subtotal."
                ),
            )

            return

        total = subtotal - descuento

        payment_summary = []
        for method in SaleService.PAYMENT_METHODS:
            amount = sum(
                item["cantidad"] * item["precio_unitario"]
                for item in self.items
                if item["metodo_pago"] == method
            )
            if amount:
                paid_amount = amount * total / subtotal if subtotal else 0.0
                payment_summary.append(f"{method}: $ {paid_amount:,.2f}")

        confirmacion = QMessageBox.question(
            self,
            "Confirmar venta",
            (
                f"¿Confirmar venta por "
                f"$ {total:,.2f}?\n\n"
                "Formas de pago:\n"
                + "\n".join(payment_summary)
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if (
            confirmacion
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:

            venta = self.service.create_sale(
                items=self.items,
                discount=descuento,
            )

        except (
            ValueError,
            RuntimeError,
        ) as exc:

            QMessageBox.critical(
                self,
                "No se pudo registrar la venta",
                str(exc),
            )

            return

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Error inesperado",
                (
                    "Ocurrió un error al "
                    "registrar la venta:\n"
                    f"{exc}"
                ),
            )

            return

        mensaje = (
            "Venta registrada correctamente.\n\n"
            f"Folio: {venta['folio']}\n"
            f"Total: $ {venta['total']:,.2f}\n"
            "Forma de pago: "
            f"{venta['metodo_pago']}\n"
        )

        if venta["monto_comision"] > 0:
            mensaje += (
                f"Comisión: "
                f"$ {venta['monto_comision']:,.2f}\n"
                f"Neto: "
                f"$ {venta['total_neto']:,.2f}"
            )

        QMessageBox.information(
            self,
            "Venta registrada",
            mensaje,
        )

        self.last_sale_id = int(venta["id"])
        self.ticket_button.setEnabled(True)

        self._limpiar_venta()

    def _guardar_ultimo_ticket(self) -> None:
        if self.last_sale_id is None:
            return

        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar ticket de venta",
            "ticket_venta.pdf",
            "Documento PDF (*.pdf)",
        )
        if not destination:
            return

        try:
            output_path = self.ticket_service.generate_sale_ticket(
                self.last_sale_id,
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

    def _limpiar_venta(self) -> None:

        self.items.clear()

        self.descuento.setValue(0)

        self._refrescar_tabla()

        self.codigo_input.clear()
        self.codigo_input.setFocus()

    def focus_input(self) -> None:
        self.codigo_input.setFocus()
