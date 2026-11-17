from typing import Optional

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QRegularExpressionValidator

from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QHBoxLayout,
    QPushButton,
    QInputDialog,
    QListWidget,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from app.services.product_service import ProductService


class ProductNumericInput(QLineEdit):
    """Cantidad o precio editable sin flechas ni restauración de valores.

    Un campo vacío significa cero al guardar, pero permanece visualmente
    vacío después de Backspace y de perder el foco.
    """

    def __init__(self, decimals: int, currency: bool = False) -> None:
        super().__init__()
        self.decimals = decimals
        self.clear_on_focus = True
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setValidator(QRegularExpressionValidator(
            QRegularExpression(
                rf"[0-9]{{0,9}}(?:\.[0-9]{{0,{decimals}}})?"
            ),
            self,
        ))
        self.setPlaceholderText("0.00" if currency else "0")
        self.currency_prefix = QLabel("$", self) if currency else None
        if self.currency_prefix is not None:
            self.currency_prefix.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            self.currency_prefix.setStyleSheet(
                "background: transparent; border: none; padding: 0;"
            )
            self.setTextMargins(22, 0, 6, 0)
        self.setToolTip(
            ("Importe en pesos" if currency else "Cantidad")
            + f"; hasta {decimals} decimales. Vacío equivale a cero."
        )
        self.setMinimumHeight(32)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.currency_prefix is not None:
            self.currency_prefix.setGeometry(7, 0, 13, self.height())

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        if self.clear_on_focus:
            self.clear()
        else:
            # En edición conserva el dato si el usuario sólo pasa por él.
            self.selectAll()

    def value(self) -> float:
        text = self.text().strip()
        return float(text) if text else 0.0

    def setValue(self, value: float) -> None:
        number = float(value or 0)
        self.setText(f"{number:.{self.decimals}f}")


class CatalogManagerDialog(QDialog):
    """Administra categorías o unidades sin borrar valores históricos."""

    def __init__(self, service: ProductService, kind: str, parent=None):
        super().__init__(parent)
        self.service = service
        self.kind = kind
        self.setWindowTitle(
            "Administrar categorías" if kind == "categorias"
            else "Administrar unidades"
        )
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        help_label = QLabel(
            "Al eliminar una opción, dejará de estar disponible para nuevos "
            "productos. Los productos existentes y sus historiales la conservarán."
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.options = QListWidget()
        layout.addWidget(self.options)
        actions = QHBoxLayout()
        add_button = QPushButton("Agregar")
        remove_button = QPushButton("Eliminar")
        close_button = QPushButton("Cerrar")
        add_button.clicked.connect(self._add)
        remove_button.clicked.connect(self._remove)
        close_button.clicked.connect(self.accept)
        actions.addWidget(add_button)
        actions.addWidget(remove_button)
        actions.addStretch()
        actions.addWidget(close_button)
        layout.addLayout(actions)
        self._refresh()

    def _catalog(self):
        return (self.service.get_categories() if self.kind == "categorias"
                else self.service.get_units())

    def _refresh(self):
        self.options.clear()
        from PySide6.QtCore import Qt
        for item in self._catalog():
            self.options.addItem(item["nombre"])
            self.options.item(self.options.count() - 1).setData(
                Qt.ItemDataRole.UserRole, item["id"]
            )

    def _add(self):
        name, ok = QInputDialog.getText(
            self, "Agregar opción", "Nombre:"
        )
        if not ok:
            return
        try:
            option_id = self.service.add_catalog_option(self.kind, name)
        except ValueError as error:
            QMessageBox.warning(self, "No se pudo agregar", str(error))
            return
        self._refresh()
        from PySide6.QtCore import Qt
        for index in range(self.options.count()):
            if self.options.item(index).data(Qt.ItemDataRole.UserRole) == option_id:
                self.options.setCurrentRow(index)
                break

    def _remove(self):
        current = self.options.currentItem()
        if current is None:
            QMessageBox.information(
                self, "Selecciona una opción",
                "Selecciona la opción que deseas eliminar."
            )
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Confirmar eliminación")
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setText(
            f"¿Quitar '{current.text()}' de las opciones disponibles?\n\n"
            "Los productos existentes y los historiales no se modificarán."
        )
        yes = confirm.addButton("Sí, eliminar", QMessageBox.ButtonRole.YesRole)
        no = confirm.addButton("No, cancelar", QMessageBox.ButtonRole.NoRole)
        confirm.setDefaultButton(no)
        confirm.setEscapeButton(no)
        confirm.exec()
        if confirm.clickedButton() is not yes:
            return
        from PySide6.QtCore import Qt
        try:
            self.service.remove_catalog_option(
                self.kind, current.data(Qt.ItemDataRole.UserRole)
            )
        except ValueError as error:
            QMessageBox.warning(self, "No se pudo eliminar", str(error))
            return
        self._refresh()


class ProductDialog(QDialog):
    """Formulario de alta y edición de productos."""

    def __init__(
        self,
        product_service: ProductService,
        product: Optional[dict] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.product_service = product_service
        self.product = product
        self._custom_service_profit = bool(product and product.get("tipo") == "SERVICIO")

        self.setWindowTitle(
            "Editar producto" if product else "Nuevo producto"
        )

        self.setMinimumWidth(500)

        self._create_widgets()
        self._load_catalogs()
        self.tipo.currentIndexChanged.connect(self._toggle_kind)
        self.subtipo_servicio.currentIndexChanged.connect(self._service_subtype_changed)
        self.precio.textChanged.connect(self._price_changed)
        self.utilidad_servicio.textEdited.connect(self._mark_custom_profit)
        self.utilidad_servicio.textChanged.connect(self._update_service_profit_hint)
        if product:
            for field in (
                self.costo, self.precio, self.existencia, self.stock_minimo
            ):
                field.clear_on_focus = False
        else:
            self.nombre.editingFinished.connect(self._fill_from_matching_name)
            # Sugerencias del catálogo, pero solo la coincidencia exacta
            # rellena los demás campos al terminar la captura del nombre.
            product_names = sorted(
                {p["nombre"] for p in self.product_service.list_products()},
                key=str.casefold,
            )
            self.name_completer = QCompleter(product_names, self.nombre)
            self.name_completer.setCaseSensitivity(
                Qt.CaseSensitivity.CaseInsensitive
            )
            self.name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.nombre.setCompleter(self.name_completer)
            self.name_completer.activated.connect(
                self._fill_from_matching_name
            )
        if not product:
            self.unidad.setCurrentText("pieza")

        if product:
            self._load_product(product)
        else:
            self.codigo.setText(
                self.product_service.get_next_internal_code()
            )
        self._toggle_kind()

    def _create_widgets(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.tipo = QComboBox()
        self.tipo.addItem("Producto físico (con existencias)", "PRODUCTO")
        self.tipo.addItem("Servicio (sin inventario)", "SERVICIO")
        self.subtipo_servicio = QComboBox()
        for service_type in ProductService.SERVICE_TYPES:
            self.subtipo_servicio.addItem(service_type)
        self.tipo_info = QLabel(
            "Los servicios no consumen inventario. Puedes vender varios "
            "servicios y productos en un mismo cobro."
        )
        self.tipo_info.setWordWrap(True)

        self.codigo = QLineEdit()
        self.codigo.setReadOnly(True)
        self.codigo.setToolTip(
            "El código interno se asigna automáticamente al guardar."
        )

        self.codigo_barras = QLineEdit()
        self.codigo_barras.setPlaceholderText(
            "Escanea el código de barras aquí"
        )

        self.codigo_qr = QLineEdit()
        self.codigo_qr.setPlaceholderText("Escanea el código QR existente aquí")

        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Nombre del producto")
        self._filled_source_id: int | None = None
        self._last_checked_name = ""
        self.prefill_hint = QLabel("")
        self.prefill_hint.setWordWrap(True)
        self.codigo_barras.returnPressed.connect(self.codigo_qr.setFocus)
        self.codigo_qr.returnPressed.connect(self.nombre.setFocus)

        self.categoria = QComboBox()
        self.categoria.setEditable(False)

        self.marca = QLineEdit()
        self.color = QLineEdit()

        self.unidad = QComboBox()


        self.costo = self._create_money_spinbox()
        self.precio = self._create_money_spinbox()

        self.existencia = self._create_quantity_spinbox()
        self.stock_minimo = self._create_quantity_spinbox()
        self.utilidad_servicio = self._create_money_spinbox()
        self.utilidad_servicio.setToolTip(
            "Ganancia bruta que deseas registrar por cada servicio. "
            "El sistema calcula el costo interno como precio menos utilidad."
        )
        self.utilidad_info = QLabel()
        self.utilidad_info.setWordWrap(True)

        self.proveedor = QComboBox()
        self.proveedor.setEditable(False)

        form.addRow("Tipo de registro:", self.tipo)
        form.addRow("Clase de servicio:", self.subtipo_servicio)
        form.addRow("", self.tipo_info)
        form.addRow("Código interno:", self.codigo)
        form.addRow("Código de barras:", self.codigo_barras)
        form.addRow("Código QR:", self.codigo_qr)
        form.addRow("Nombre:", self.nombre)
        form.addRow("", self.prefill_hint)
        category_row = QHBoxLayout()
        category_row.addWidget(self.categoria, 1)
        manage_categories = QPushButton("Administrar...")
        manage_categories.clicked.connect(self._manage_categories)
        category_row.addWidget(manage_categories)
        form.addRow("Categoría:", category_row)
        form.addRow("Marca:", self.marca)
        form.addRow("Color:", self.color)
        unit_row = QHBoxLayout()
        unit_row.addWidget(self.unidad, 1)
        manage_units = QPushButton("Administrar...")
        manage_units.clicked.connect(self._manage_units)
        unit_row.addWidget(manage_units)
        form.addRow("Unidad:", unit_row)
        form.addRow("Costo interno:", self.costo)
        form.addRow("Precio al cliente:", self.precio)
        form.addRow("Utilidad por servicio:", self.utilidad_servicio)
        form.addRow("", self.utilidad_info)
        form.addRow("Existencia:", self.existencia)
        form.addRow("Stock mínimo:", self.stock_minimo)
        form.addRow("Proveedor:", self.proveedor)

        self.form = form
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    @staticmethod
    def _create_money_spinbox() -> ProductNumericInput:
        return ProductNumericInput(decimals=2, currency=True)

    @staticmethod
    def _create_quantity_spinbox() -> ProductNumericInput:
        return ProductNumericInput(decimals=3)

    def _toggle_kind(self, *_args) -> None:
        service = self.tipo.currentData() == "SERVICIO"
        for field in (self.subtipo_servicio, self.tipo_info,
                      self.utilidad_servicio, self.utilidad_info):
            field.setVisible(service)
            label = self.form.labelForField(field)
            if label is not None:
                label.setVisible(service)
        for field in (self.costo, self.existencia, self.stock_minimo):
            field.setVisible(not service)
            label = self.form.labelForField(field)
            if label is not None:
                label.setVisible(not service)
        self.categoria.setEnabled(not service)
        if service and not self._custom_service_profit:
            self.utilidad_servicio.setValue(self.precio.value())
        self._update_service_profit_hint()

    def _service_subtype_changed(self, *_args) -> None:
        self._update_service_profit_hint()

    def _mark_custom_profit(self, *_args) -> None:
        self._custom_service_profit = True

    def _price_changed(self, *_args) -> None:
        if self.tipo.currentData() == "SERVICIO" and not self._custom_service_profit:
            self.utilidad_servicio.setValue(self.precio.value())
        self._update_service_profit_hint()

    def _update_service_profit_hint(self, *_args) -> None:
        if self.tipo.currentData() == "SERVICIO":
            price = self.precio.value()
            profit = self.utilidad_servicio.value()
            self.utilidad_info.setText(
                f"Precio: $ {price:,.2f} | Utilidad bruta: $ {profit:,.2f} | "
                f"Costo interno: $ {price-profit:,.2f}. "
                "La utilidad final puede variar por descuentos y comisiones."
            )

    def _fill_from_matching_name(self, _selection: str = "") -> None:
        """Sugiere campos de un producto homónimo sin modificar el original."""
        if self.product is not None:
            return

        name = self.nombre.text().strip()
        normalized = " ".join(name.split()).casefold()
        if not normalized or normalized == self._last_checked_name:
            return
        self._last_checked_name = normalized

        existing = self.product_service.find_existing_by_name(name)
        if existing is None:
            self.prefill_hint.clear()
            self._filled_source_id = None
            return

        self._filled_source_id = int(existing["id"])
        unavailable = []

        category_id = existing.get("categoria_id")
        index = self.categoria.findData(category_id)
        if index >= 0:
            self.categoria.setCurrentIndex(index)
        else:
            unavailable.append("categoría")

        unit = existing.get("unidad") or ""
        index = self.unidad.findText(unit)
        if index >= 0:
            self.unidad.setCurrentIndex(index)
        else:
            unavailable.append("unidad")

        self.marca.setText(existing.get("marca") or "")
        if existing.get("tipo") == "SERVICIO":
            self.tipo.setCurrentIndex(self.tipo.findData("SERVICIO"))
            self.subtipo_servicio.setCurrentText(
                existing.get("subtipo_servicio") or "Otros servicios"
            )
            self._custom_service_profit = True
        self.costo.setValue(existing.get("costo") or 0)
        self.precio.setValue(existing.get("precio") or 0)
        if existing.get("tipo") == "SERVICIO":
            self.utilidad_servicio.setValue(
                max(0, self.precio.value() - self.costo.value())
            )
        self.stock_minimo.setValue(existing.get("stock_minimo") or 0)

        supplier_id = existing.get("proveedor_id")
        index = self.proveedor.findData(supplier_id)
        if index >= 0:
            self.proveedor.setCurrentIndex(index)
        else:
            unavailable.append("proveedor")

        # No copiar código interno, códigos de barras/QR, color o existencia.
        # Cada nuevo artículo debe conservar su propia identidad y stock.
        message = (
            f"Datos sugeridos de {existing['codigo']}. "
            "Puedes modificar cualquiera de los campos antes de guardar."
        )
        if unavailable:
            message += (
                " Revisa " + ", ".join(unavailable)
                + ": la opción del producto original ya no está disponible."
            )
        self.prefill_hint.setText(message)

    def _manage_categories(self) -> None:
        original_id = self.categoria.currentData()
        CatalogManagerDialog(
            self.product_service, "categorias", parent=self
        ).exec()
        self._load_catalogs()
        index = self.categoria.findData(original_id)
        if index >= 0:
            self.categoria.setCurrentIndex(index)
        elif self.product:
            self.categoria.addItem(
                self.product.get("categoria_nombre") or "Categoría anterior",
                original_id,
            )
            self.categoria.setCurrentIndex(self.categoria.count() - 1)

    def _manage_units(self) -> None:
        original_unit = self.unidad.currentText()
        CatalogManagerDialog(
            self.product_service, "unidades", parent=self
        ).exec()
        self._load_catalogs()
        index = self.unidad.findText(original_unit)
        if index >= 0:
            self.unidad.setCurrentIndex(index)
        elif self.product and original_unit:
            self.unidad.addItem(original_unit)
            self.unidad.setCurrentText(original_unit)

    def _load_catalogs(self) -> None:
        self.categoria.clear()

        for category in self.product_service.get_categories():
            self.categoria.addItem(
                category["nombre"],
                category["id"],
            )

        self.unidad.clear()
        for unit in self.product_service.get_units():
            self.unidad.addItem(unit["nombre"])

        self.proveedor.clear()
        self.proveedor.addItem("Sin proveedor", None)

        for supplier in self.product_service.get_suppliers():
            self.proveedor.addItem(
                supplier["nombre"],
                supplier["id"],
            )

    def _load_product(self, product: dict) -> None:
        kind = product.get("tipo") or "PRODUCTO"
        self.tipo.setCurrentIndex(self.tipo.findData(kind))
        if kind == "SERVICIO":
            self.subtipo_servicio.setCurrentText(
                product.get("subtipo_servicio") or "Otros servicios"
            )
        self.codigo.setText(product["codigo"])
        self.codigo_barras.setText(product["codigo_barras"] or "")
        self.codigo_qr.setText(product["codigo_qr"] or "")
        self.nombre.setText(product["nombre"])
        self.marca.setText(product["marca"] or "")
        self.color.setText(product["color"] or "")

        unidad_index = self.unidad.findText(product["unidad"])

        if unidad_index < 0 and product["unidad"]:
            self.unidad.addItem(product["unidad"])
            unidad_index = self.unidad.findText(product["unidad"])
        if unidad_index >= 0:
            self.unidad.setCurrentIndex(unidad_index)

        self.costo.setValue(float(product["costo"] or 0))
        self.precio.setValue(float(product["precio"] or 0))
        self.existencia.setValue(float(product["existencia"] or 0))
        self.stock_minimo.setValue(float(product["stock_minimo"] or 0))
        if kind == "SERVICIO":
            self.utilidad_servicio.setValue(
                max(0, self.precio.value() - self.costo.value())
            )

        category_id = product.get("categoria_id")

        if category_id is not None:
            index = self.categoria.findData(category_id)

            if index < 0:
                # Valor retirado: mostrarlo en la edición, sin perder el dato.
                self.categoria.addItem(
                    product.get("categoria_nombre") or "Categoría anterior",
                    category_id,
                )
                index = self.categoria.findData(category_id)
            self.categoria.setCurrentIndex(index)

        supplier_id = product.get("proveedor_id")

        if supplier_id is not None:
            index = self.proveedor.findData(supplier_id)

            if index >= 0:
                self.proveedor.setCurrentIndex(index)

    def _save(self) -> None:
        codigo = self.codigo.text().strip()
        nombre = self.nombre.text().strip()

        if not codigo:
            QMessageBox.warning(
                self,
                "Dato faltante",
                "El código interno es obligatorio.",
            )
            self.codigo.setFocus()
            return

        if not nombre:
            QMessageBox.warning(
                self,
                "Dato faltante",
                "El nombre del producto es obligatorio.",
            )
            self.nombre.setFocus()
            return

        service = self.tipo.currentData() == "SERVICIO"
        if (not service and self.categoria.currentData() is None) or not self.unidad.currentText():
            QMessageBox.warning(self, "Dato faltante",
                "Selecciona una categoría y una unidad válidas.")
            return

        if service:
            price = self.precio.value()
            profit = self.utilidad_servicio.value()
            if profit > price:
                QMessageBox.warning(
                    self, "Utilidad inválida",
                    "La utilidad por servicio no puede superar el precio al cliente."
                )
                return
            cost = round(price - profit, 2)
        else:
            cost = self.costo.value()

        data = {
            "tipo": self.tipo.currentData(),
            "subtipo_servicio": self.subtipo_servicio.currentText() if service else None,
            "codigo": codigo,
            "codigo_barras": self.codigo_barras.text().strip(),
            "codigo_qr": self.codigo_qr.text().strip(),
            "nombre": nombre,
            "categoria_id": (
                (self.product.get("categoria_id") if self.product else None)
                if service else self.categoria.currentData()
            ),
            "marca": self.marca.text().strip(),
            "color": self.color.text().strip(),
            "unidad": self.unidad.currentText(),
            "costo": cost,
            "precio": self.precio.value(),
            "existencia": 0 if service else self.existencia.value(),
            "stock_minimo": 0 if service else self.stock_minimo.value(),
            "proveedor_id": self.proveedor.currentData(),
        }

        if not self.product:
            duplicate = self.product_service.find_duplicate_product(data)
            if duplicate is not None:
                status = (
                    " (desactivado)" if not duplicate["activo"] else ""
                )
                QMessageBox.warning(
                    self,
                    "Producto duplicado",
                    "Ya existe un producto con el mismo Nombre, Categoría, "
                    "Marca, Color y Unidad.\n\n"
                    f"Producto: {duplicate['nombre']}\n"
                    f"Código: {duplicate['codigo']}{status}\n\n"
                    "No se puede registrar nuevamente. "
                    "Revisa los datos o utiliza el producto existente.",
                )
                self.color.setFocus()
                return

        if (self.product and service and
                self.product.get("tipo") != "SERVICIO" and
                float(self.product.get("existencia") or 0) != 0):
            reply = QMessageBox.question(
                self, "Convertir a servicio",
                "Se quitará del inventario la existencia actual "
                f"({float(self.product['existencia']):g}) de este registro. "
                "Las ventas y compras anteriores se conservarán. "
                "¿Quieres convertirlo a servicio?"
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            if self.product:
                self.product_service.update_product(
                    self.product["id"],
                    data,
                )
            else:
                self.product_service.create_product(data)

        except ValueError as error:
            QMessageBox.warning(
                self,
                "No se pudo guardar",
                str(error),
            )
            return

        except Exception as error:
            QMessageBox.critical(
                self,
                "No se pudo guardar",
                f"No fue posible guardar el producto.\n\n{error}",
            )
            return

        self.accept()
