from PySide6.QtCore import QTimer, Signal, QStringListModel, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QCompleter,
    QComboBox,
    QDialog,
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
from app.services.sale_cart_service import (
    calculate_discount,
    expand_sale_items,
    group_sale_items,
    has_available_inventory,
)
from app.services.sale_service import SaleService
from app.services.ticket_service import TicketService


class ClearOnFocusLineEdit(QLineEdit):
    """Limpia la búsqueda anterior al iniciar una nueva captura."""

    def focusInEvent(self, event) -> None:
        self.clear()
        super().focusInEvent(event)


class SalePaymentDialog(QDialog):
    """Captura los pagos de toda la venta y calcula el cambio."""

    def __init__(self, total: float, commission_rate: float, parent=None):
        super().__init__(parent)
        from app.services.payment_allocation import calculate_payment
        self.calculate_payment = calculate_payment
        self.total = round(total, 2)
        self.commission_rate = commission_rate
        self.result = None
        self.setWindowTitle("Cobrar venta")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        title = QLabel(f"Total a cobrar: $ {self.total:,.2f}")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)
        help_text = QLabel(
            "Distribuye el total entre efectivo, transferencia y tarjeta. "
            "El efectivo recibido puede ser mayor que el importe en efectivo."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.amounts = {}
        for name in SaleService.PAYMENT_METHODS:
            row = QHBoxLayout()
            row.addWidget(QLabel("Tarjeta (Mercado Libre)" if name == "Mercado Libre" else name))
            field = QDoubleSpinBox()
            field.setDecimals(2)
            field.setRange(0, 99999999.99)
            field.setPrefix("$ ")
            field.setMinimumHeight(38)
            field.valueChanged.connect(self._update)
            row.addWidget(field)
            self.amounts[name] = field
            layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Efectivo recibido"))
        self.cash_received = QDoubleSpinBox()
        self.cash_received.setDecimals(2)
        self.cash_received.setRange(0, 99999999.99)
        self.cash_received.setPrefix("$ ")
        self.cash_received.valueChanged.connect(self._update)
        row.addWidget(self.cash_received)
        layout.addLayout(row)
        self.remaining_label = QLabel()
        self.change_label = QLabel()
        self.change_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.commission_label = QLabel()
        for widget in (self.remaining_label, self.change_label, self.commission_label):
            layout.addWidget(widget)
        controls = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        self.confirm = QPushButton("Confirmar cobro")
        self.confirm.clicked.connect(self._accept)
        controls.addWidget(cancel)
        controls.addWidget(self.confirm)
        layout.addLayout(controls)
        self.amounts["Efectivo"].setValue(self.total)
        self.cash_received.setValue(self.total)
        self._update()

    def _update(self):
        from app.services.payment_allocation import cents
        amount_cents = sum(cents(field.value()) for field in self.amounts.values())
        remaining = cents(self.total) - amount_cents
        received = cents(self.cash_received.value())
        cash = cents(self.amounts["Efectivo"].value())
        self.remaining_label.setText(
            f"{'Falta cobrar' if remaining >= 0 else 'Excede el total'}: "
            f"$ {abs(remaining) / 100:,.2f}"
        )
        self.change_label.setText(f"Cambio: $ {max(0, received - cash) / 100:,.2f}")
        card = self.amounts["Mercado Libre"].value()
        self.commission_label.setText(
            f"Comisión estimada de tarjeta ({self.commission_rate:g}%): "
            f"$ {round(card * self.commission_rate / 100, 2):,.2f}"
        )
        self.confirm.setEnabled(remaining == 0 and received >= cash)

    def _accept(self):
        payments = {name: field.value() for name, field in self.amounts.items()}
        try:
            self.result = self.calculate_payment(
                self.total, payments, self.cash_received.value(),
                self.commission_rate,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Cobro inválido", str(exc))
            return
        self.accept()


class SaleItemsTable(QTableWidget):
    """Tabla del carrito con eliminación rápida mediante la tecla D."""

    delete_requested = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_D:
            self.delete_requested.emit()
            return
        super().keyPressEvent(event)


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
        self.discount_mode = "Monto"
        self.ignore_next_return = False

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

        self.codigo_input = ClearOnFocusLineEdit()
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

        mode_layout = QHBoxLayout()
        self.venta_voluminosa = QCheckBox("Venta voluminosa")
        self.venta_voluminosa.setToolTip(
            "Agrupa en una fila las unidades del mismo producto."
        )
        self.venta_voluminosa.toggled.connect(
            self._cambiar_modo_volumen
        )
        mode_help = QLabel(
            "Desactivada: cada unidad se muestra por separado."
        )
        mode_help.setStyleSheet("color: #94A3B8;")
        mode_layout.addWidget(self.venta_voluminosa)
        mode_layout.addWidget(mode_help)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        self.tabla = SaleItemsTable(0, 9)

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
                "",
            ]
        )

        self.tabla.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.tabla.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.tabla.delete_requested.connect(self._quitar_fila_seleccionada)

        self.tabla.verticalHeader().setVisible(False)

        self.tabla.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )

        self.tabla.horizontalHeader().setSectionResizeMode(
            8,
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

        self.descuento_tipo = QComboBox()
        self.descuento_tipo.addItems(("Monto", "Porcentaje"))
        self.descuento_tipo.setMinimumHeight(36)
        self.descuento_tipo.currentTextChanged.connect(
            self._cambiar_tipo_descuento
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

        controles_layout.addWidget(self.descuento_tipo)

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
        if self.ignore_next_return:
            self.ignore_next_return = False
            self.codigo_input.clear()
            return

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
            # Enter sobre el popup también dispara returnPressed en QLineEdit.
            # La bandera evita procesar esa misma pulsación por segunda vez y
            # se restablece al terminar el evento, para no ignorar otro escaneo.
            self.ignore_next_return = True
            self._agregar_producto(product)
            QTimer.singleShot(0, self._reset_return_guard)

    def _reset_return_guard(self) -> None:
        self.ignore_next_return = False

    def _agregar_producto(self, producto: dict) -> None:
        if not self._hay_inventario_disponible(producto):
            self._mostrar_sin_inventario()
            self.codigo_input.setFocus()
            return

        if self.venta_voluminosa.isChecked():
            for item in self.items:
                if item["producto_id"] == producto["id"]:
                    item["cantidad"] = float(item["cantidad"]) + 1
                    self._refrescar_tabla()
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
            }
        )

        self._refrescar_tabla()

        self.codigo_input.clear()
        self.codigo_input.setFocus()

    def _hay_inventario_disponible(self, producto: dict) -> bool:
        return has_available_inventory(
            producto["id"], producto["existencia"], self.items
        )

    def _mostrar_sin_inventario(self) -> None:
        QMessageBox.warning(
            self,
            "Sin inventario",
            "¡Ya no hay inventario disponible! Favor de agregar más producto",
        )

    def _cambiar_modo_volumen(self, checked: bool) -> None:
        if checked:
            self.items, _ = group_sale_items(self.items)
        else:
            self.items = expand_sale_items(self.items)
        self._refrescar_tabla()

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

            quitar = QPushButton("Quitar")

            quitar.clicked.connect(
                lambda checked=False, index=row:
                self._quitar_item(index)
            )

            self.tabla.setCellWidget(
                row,
                8,
                quitar,
            )

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

    def _quitar_fila_seleccionada(self) -> None:
        row = self.tabla.currentRow()
        if row >= 0:
            self._quitar_item(row)

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

        descuento = self._calcular_descuento(subtotal)

        total = max(
            0.0,
            subtotal - descuento,
        )

        neto = total

        self.subtotal_label.setText(
            f"Subtotal:  $ {subtotal:,.2f}"
        )

        self.comision_label.setText("Comisión de tarjeta: se calcula al cobrar")

        self.total_label.setText(
            f"TOTAL A COBRAR:  $ {total:,.2f}"
        )

        self.neto_label.setText(
            (
                "Neto para Echando Chal:  "
                f"$ {neto:,.2f}"
            )
        )

    def _calcular_descuento(self, subtotal: float | None = None) -> float:
        subtotal = self._calcular_subtotal() if subtotal is None else subtotal
        return calculate_discount(
            subtotal, self.descuento.value(), self.discount_mode
        )

    def _cambiar_tipo_descuento(self, new_mode: str) -> None:
        subtotal = self._calcular_subtotal()
        current_discount = self._calcular_descuento(subtotal)
        self.discount_mode = new_mode
        self.descuento.blockSignals(True)
        if new_mode == "Porcentaje":
            self.descuento.setRange(0, 100)
            self.descuento.setPrefix("")
            self.descuento.setSuffix(" %")
            value = (current_discount / subtotal * 100) if subtotal else 0
        else:
            self.descuento.setRange(0, 999999.99)
            self.descuento.setSuffix("")
            self.descuento.setPrefix("$ ")
            value = current_discount
        self.descuento.setValue(value)
        self.descuento.blockSignals(False)
        self._actualizar_totales()

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

        descuento = self._calcular_descuento(subtotal)

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

        if total <= 0:
            QMessageBox.warning(self, "Total inválido", "La venta debe ser mayor que cero.")
            return
        dialog = SalePaymentDialog(total, self.service.get_commission_rate(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payment_info = dialog.result
        if payment_info is None:
            return

        try:

            venta = self.service.create_sale(
                items=self.items,
                discount=descuento,
                payments=payment_info["payments"],
                cash_received=payment_info["cash_received"],
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

        mensaje += f"Cambio para el cliente: $ {venta['change']:,.2f}\n"

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

        self.descuento_tipo.setCurrentText("Monto")
        self.descuento.setValue(0)

        self._refrescar_tabla()

        self.codigo_input.clear()
        self.codigo_input.setFocus()

    def focus_input(self) -> None:
        self.codigo_input.setFocus()
