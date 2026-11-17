from PySide6.QtCore import QTimer, Signal, QStringListModel, Qt, QRegularExpression
from PySide6.QtGui import QIntValidator, QRegularExpressionValidator
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCompleter,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
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
    set_sale_quantity,
    calculate_discount,
    has_available_inventory,
)
from app.services.sale_service import SaleService
from app.services.ticket_service import TicketService
from app.ui.sale_receipt_prompt import SaleReceiptPrompt
from app.ui.ticket_preview_dialog import print_sale_ticket_to_printer


SALE_QUANTITY_HELP = (
    "Para cambiar la cantidad final de este producto, selecciona el renglón "
    "y presiona C, o haz doble clic. Escribe la nueva cantidad (entera) y "
    "presiona Enter para aplicar. Escribe 0 para quitar la fila."
)


class ClearOnFocusQuantityInput(QLineEdit):
    """Al entrar al campo permite capturar un nuevo valor desde cero."""

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.clear()


class SaleQuantityDialog(QDialog):
    """Edición directa de la cantidad final con captura entera y Enter."""

    def __init__(
        self, items: list[dict], row: int, stock: float, parent=None
    ) -> None:
        super().__init__(parent)
        self.items = items
        self.row = row
        self.stock = float(stock)
        self.new_quantity: int | None = None
        item = items[row]
        current = int(item["cantidad"])
        other_quantity = sum(
            float(line["cantidad"])
            for index, line in enumerate(items)
            if index != row
            and int(line["producto_id"]) == int(item["producto_id"])
        )
        available_for_row = max(0, int(self.stock - other_quantity))

        self.setWindowTitle("Modificar cantidad")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(11)

        product = QLabel(item["nombre"])
        product.setStyleSheet("font-size: 18px; font-weight: bold;")
        product.setWordWrap(True)
        layout.addWidget(product)

        current_info = QLabel(
            f"Cantidad actual: {current}    |    "
            + ("Servicio sin límite de inventario"
               if item.get("tipo") == "SERVICIO"
               else f"Máximo en este renglón: {available_for_row}")
        )
        layout.addWidget(current_info)

        layout.addWidget(QLabel("Nueva cantidad:"))
        self.quantity = ClearOnFocusQuantityInput(self)
        self.quantity.setAccessibleName("Nueva cantidad final del producto")
        self.quantity.setPlaceholderText("Escribe la cantidad final")
        self.quantity.setValidator(QIntValidator(0, 999999, self.quantity))
        self.quantity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quantity.setMinimumHeight(42)
        self.quantity.setText(str(current))
        layout.addWidget(self.quantity)

        help_label = QLabel("Solo números enteros. Escribe 0 para quitar la fila.")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        self.preview = QLabel()
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        self.apply_button = QPushButton("Aplicar cantidad")
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self._accept_quantity)
        buttons.addWidget(cancel)
        buttons.addWidget(self.apply_button)
        layout.addLayout(buttons)

        self.quantity.textChanged.connect(self._update_preview)
        self.quantity.returnPressed.connect(self._accept_quantity)
        self._update_preview()
        # El campo queda listo para escribir; al recibir foco se limpia.
        self.quantity.setFocus()

    def _requested_quantity(self) -> int | None:
        text = self.quantity.text().strip()
        if not text or not text.isascii() or not text.isdecimal():
            return None
        return int(text)

    def _update_preview(self, _text: str = "") -> None:
        requested = self._requested_quantity()
        if requested is None:
            self.preview.setText("Ingresa la cantidad final del producto.")
            self.apply_button.setEnabled(False)
            return
        try:
            final_quantity = set_sale_quantity(
                self.items, self.row, requested, self.stock
            )
        except ValueError as error:
            self.preview.setText(str(error))
            self.apply_button.setEnabled(False)
            return

        if final_quantity == 0:
            self.preview.setText("Se quitará este renglón de la venta.")
        else:
            price = float(self.items[self.row]["precio_unitario"])
            importe = round(final_quantity * price, 2)
            self.preview.setText(f"Nuevo importe: $ {importe:,.2f}")
        self.apply_button.setEnabled(True)

    def _accept_quantity(self) -> None:
        requested = self._requested_quantity()
        if requested is None:
            return
        try:
            self.new_quantity = set_sale_quantity(
                self.items, self.row, requested, self.stock
            )
        except ValueError as error:
            self.preview.setText(str(error))
            self.apply_button.setEnabled(False)
            self.new_quantity = None
            return
        self.accept()


class ClearOnFocusDiscountSpinBox(QDoubleSpinBox):
    """Descuento numérico sin flechas, listo para escribir al recibir foco."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        # El descuento anterior deja de aplicarse al empezar una nueva captura.
        # clear() mantiene el prefijo o sufijo del modo actual, sin mostrar 0.00.
        self.setValue(0)
        self.clear()

    def wheelEvent(self, event) -> None:
        # Evita variar el importe por un giro accidental de la rueda del mouse.
        event.ignore()


class ClearOnFocusLineEdit(QLineEdit):
    """Limpia la búsqueda anterior al iniciar una nueva captura."""

    def focusInEvent(self, event) -> None:
        self.clear()
        super().focusInEvent(event)


class PaymentAmountInput(QLineEdit):
    """Entrada monetaria libre de flechas, vacía al iniciar y al enfocarse.

    La ausencia de texto equivale a 0 solo para el cálculo provisional.
    No se escribe ningún monto automáticamente en los campos.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Escribe el monto")
        self.setValidator(
            QRegularExpressionValidator(
                QRegularExpression(r"\d{0,8}(?:\.\d{0,2})?"),
                self,
            )
        )
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setMinimumHeight(38)
        self.setMinimumWidth(175)
        # Prefijo puramente visual: nunca se almacena en el texto ni altera
        # la validación, los centavos, el cambio o el cálculo de comisión.
        self.currency_prefix = QLabel("$", self)
        self.currency_prefix.setObjectName("currencyPrefix")
        self.currency_prefix.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self.currency_prefix.setStyleSheet(
            "background: transparent; border: none; padding: 0;"
        )
        self.setTextMargins(28, 0, 8, 0)
        self.setToolTip("Escribe el monto en pesos, con hasta dos decimales.")
        self._position_currency_prefix()

    def _position_currency_prefix(self) -> None:
        self.currency_prefix.setGeometry(10, 0, 18, self.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_currency_prefix()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        # No se selecciona el texto anterior: se elimina para captura nueva.
        self.clear()

    def amount(self) -> float:
        text = self.text().strip()
        return float(text) if text else 0.0


class SalePaymentDialog(QDialog):
    """Cobro simple: captura electrónica y efectivo recibido, con cambio automático."""

    def __init__(self, total: float, commission_rate: float, parent=None):
        super().__init__(parent)
        from app.services.payment_allocation import calculate_payment_from_received
        self.calculate_payment = calculate_payment_from_received
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
            "Indica lo pagado por transferencia o tarjeta y el efectivo "
            "que entrega el cliente. El sistema calcula el cambio automáticamente."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        self.amounts = {}
        amounts_grid = QGridLayout()
        amounts_grid.setHorizontalSpacing(14)
        amounts_grid.setVerticalSpacing(10)
        amounts_grid.setColumnStretch(1, 1)
        # El efectivo aplicado ya no es un campo: se calcula a partir del
        # total menos los importes de transferencia y Mercado Libre.
        for row_index, name in enumerate(("Transferencia", "Mercado Libre")):
            display_name = (
                "Tarjeta (Mercado Libre)" if name == "Mercado Libre" else name
            )
            amounts_grid.addWidget(QLabel(display_name), row_index, 0)
            field = PaymentAmountInput(self)
            field.setAccessibleName(display_name)
            field.textChanged.connect(self._update)
            amounts_grid.addWidget(field, row_index, 1)
            self.amounts[name] = field

        self.cash_received = PaymentAmountInput(self)
        self.cash_received.setAccessibleName("Efectivo recibido")
        self.cash_received.textChanged.connect(self._update)
        amounts_grid.addWidget(QLabel("Efectivo recibido"), 2, 0)
        amounts_grid.addWidget(self.cash_received, 2, 1)
        layout.addLayout(amounts_grid)

        self.cash_applied_label = QLabel()
        self.remaining_label = QLabel()
        self.change_label = QLabel()
        self.change_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.commission_label = QLabel()
        for widget in (
            self.cash_applied_label, self.remaining_label,
            self.change_label, self.commission_label,
        ):
            layout.addWidget(widget)

        controls = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        self.confirm = QPushButton("Confirmar cobro")
        self.confirm.clicked.connect(self._accept)
        controls.addWidget(cancel)
        controls.addWidget(self.confirm)
        layout.addLayout(controls)
        self._update()

    def _update(self):
        from app.services.payment_allocation import cents
        total_cents = cents(self.total)
        transfer_cents = cents(self.amounts["Transferencia"].amount())
        card_cents = cents(self.amounts["Mercado Libre"].amount())
        received_cents = cents(self.cash_received.amount())
        electronic_cents = transfer_cents + card_cents
        if electronic_cents > total_cents:
            extra = electronic_cents - total_cents
            self.cash_applied_label.setText("Efectivo aplicado a la venta: $ 0.00")
            self.remaining_label.setText(
                f"Transferencia y tarjeta exceden el total: $ {extra / 100:,.2f}"
            )
            self.change_label.setText("Cambio a devolver: $ 0.00")
            balanced = False
        else:
            required_cash = total_cents - electronic_cents
            missing = max(0, required_cash - received_cents)
            change = max(0, received_cents - required_cash)
            self.cash_applied_label.setText(
                f"Efectivo aplicado a la venta: $ {required_cash / 100:,.2f}"
            )
            self.remaining_label.setText(
                f"Falta cobrar: $ {missing / 100:,.2f}"
            )
            self.change_label.setText(
                f"Cambio a devolver: $ {change / 100:,.2f}"
            )
            balanced = missing == 0

        card_amount = self.amounts["Mercado Libre"].amount()
        self.commission_label.setText(
            f"Comisión estimada de tarjeta ({self.commission_rate:g}%): "
            f"$ {round(card_amount * self.commission_rate / 100, 2):,.2f}"
        )
        self.confirm.setEnabled(balanced)

    def _accept(self):
        try:
            self.result = self.calculate_payment(
                total=self.total,
                transfer=self.amounts["Transferencia"].amount(),
                card=self.amounts["Mercado Libre"].amount(),
                cash_received=self.cash_received.amount(),
                commission_percentage=self.commission_rate,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Cobro inválido", str(exc))
            return
        self.accept()


class SaleItemsTable(QTableWidget):
    """Tabla del carrito: D elimina y C modifica la cantidad."""

    delete_requested = Signal()
    quantity_requested = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_D:
            self.delete_requested.emit()
            return
        if (
            event.key() == Qt.Key.Key_C
            and not event.modifiers() & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        ):
            self.quantity_requested.emit()
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
        ayuda.setStyleSheet("color: palette(window-text);")
        layout.addWidget(ayuda)

        entrada_layout = QHBoxLayout()

        self.codigo_input = ClearOnFocusLineEdit()
        self.codigo_input.setPlaceholderText(
            "Código, código de barras, nombre o marca"
        )
        self.codigo_input.setToolTip(
            "Sugerencias: código | producto | marca | categoría | color | unidad"
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
        self.tabla.horizontalHeaderItem(5).setToolTip(SALE_QUANTITY_HELP)
        self.tabla.setMouseTracking(True)

        self.tabla.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.tabla.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.tabla.delete_requested.connect(self._quitar_fila_seleccionada)
        self.tabla.quantity_requested.connect(
            self._editar_cantidad_seleccionada
        )
        self.tabla.cellDoubleClicked.connect(
            self._editar_cantidad_desde_celda
        )

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

        self.descuento = ClearOnFocusDiscountSpinBox()

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
            # Mantener el código como primer campo; cada opción es única
            # y seleccionable incluso si varios productos comparten nombre.
            label = " | ".join((
                product["codigo"],
                product["nombre"],
                product.get("marca") or "Sin marca",
                product.get("categoria") or "Sin categoría",
                product.get("color") or "Sin color",
                product.get("unidad") or "Sin unidad",
            ))
            labels.append(label)
            self.suggestion_products[label] = product
        self.suggestion_model.setStringList(labels)
        if labels:
            popup = self.completer.popup()
            popup.setTextElideMode(Qt.TextElideMode.ElideNone)
            popup.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            screen = self.codigo_input.screen()
            screen_width = (
                screen.availableGeometry().width() if screen
                else self.width()
            )
            widest_label = max(
                popup.fontMetrics().horizontalAdvance(label)
                for label in labels
            )
            # Ensanchar la lista para ver los seis atributos, sin
            # exceder el ancho visible de la pantalla.
            popup.setMinimumWidth(
                max(
                    self.codigo_input.width(),
                    min(widest_label + 45, max(320, screen_width - 80)),
                )
            )
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

        self.items.append(
            {
                "producto_id": producto["id"],
                "tipo": producto.get("tipo") or "PRODUCTO",
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
        if producto.get("tipo") == "SERVICIO":
            return True
        return has_available_inventory(
            producto["id"], producto["existencia"], self.items
        )

    def _mostrar_sin_inventario(self) -> None:
        QMessageBox.warning(
            self,
            "Sin inventario",
            "¡Ya no hay inventario disponible! Favor de agregar más producto",
        )

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

            quantity_item = QTableWidgetItem(f"{item['cantidad']:g}")
            quantity_item.setToolTip(SALE_QUANTITY_HELP)
            self.tabla.setItem(row, 5, quantity_item)

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

    def _editar_cantidad_desde_celda(self, row: int, _column: int) -> None:
        self.tabla.selectRow(row)
        self._editar_cantidad(row)

    def _editar_cantidad_seleccionada(self) -> None:
        self._editar_cantidad(self.tabla.currentRow())

    def _editar_cantidad(self, row: int) -> None:
        if not 0 <= row < len(self.items):
            QMessageBox.information(
                self, "Selecciona un producto",
                "Selecciona un renglón para modificar su cantidad."
            )
            return

        stock = self.service.get_product_stock(self.items[row]["producto_id"])
        if stock is None:
            QMessageBox.warning(
                self, "Producto no disponible",
                "Este producto ya no está activo en el inventario."
            )
            return

        dialog = SaleQuantityDialog(self.items, row, stock, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._establecer_cantidad(row, dialog.new_quantity)

    def _establecer_cantidad(self, row: int, quantity: int | None) -> bool:
        """Establece la cantidad FINAL del renglón y actualiza importes."""
        if not 0 <= row < len(self.items):
            return False
        stock = self.service.get_product_stock(self.items[row]["producto_id"])
        if stock is None:
            QMessageBox.warning(
                self, "Producto no disponible",
                "Este producto ya no está activo en el inventario."
            )
            return False
        try:
            new_quantity = set_sale_quantity(
                self.items, row, quantity, stock
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cantidad no disponible", str(error))
            return False

        if new_quantity == 0:
            self.items.pop(row)
        else:
            self.items[row]["cantidad"] = new_quantity

        self._refrescar_tabla()
        if self.items:
            self.tabla.selectRow(min(row, len(self.items) - 1))
            self.tabla.setFocus()
        else:
            self.codigo_input.setFocus()
        return True

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

        # La venta ya está registrada: ninguna decisión posterior debe
        # repetir el cobro ni revertir el inventario.
        self.last_sale_id = int(venta["id"])
        self.ticket_button.setEnabled(True)
        self._limpiar_venta()

        # Una sola ventana, sin mensaje adicional, para seguir cobrando rápido.
        prompt = SaleReceiptPrompt(venta, self)
        if prompt.exec() == QDialog.DialogCode.Accepted:
            self._imprimir_ultimo_ticket()

    def _imprimir_ultimo_ticket(self) -> None:
        """Envía el recibo a la impresora predeterminada de Windows."""
        if self.last_sale_id is None:
            return

        printer_info = QPrinterInfo.defaultPrinter()
        if printer_info.isNull():
            QMessageBox.warning(
                self,
                "Impresora no configurada",
                "La venta quedó registrada, pero no hay una impresora "
                "predeterminada configurada en Windows. "
                "Puedes imprimir el ticket desde Historial de ventas.",
            )
            return

        printer = QPrinter(printer_info, QPrinter.PrinterMode.HighResolution)
        printer.setDocName(f"EchandoChal - Venta {self.last_sale_id}")
        try:
            print_sale_ticket_to_printer(
                self.ticket_service, self.last_sale_id, printer
            )
        except (OSError, RuntimeError, ValueError) as error:
            QMessageBox.warning(
                self,
                "No se pudo imprimir",
                "La venta quedó registrada correctamente. "
                f"No fue posible imprimir el recibo:\n{error}\n\n"
                "Puedes imprimirlo nuevamente desde Historial de ventas.",
            )

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
