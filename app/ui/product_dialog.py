from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QHBoxLayout,
    QPushButton,
    QInputDialog,
    QListWidget,
    QLabel,
    QWidget,
    QMessageBox,
    QVBoxLayout,
)

from app.services.product_service import ProductService


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
        confirmation = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Quitar '{current.text()}' de las opciones disponibles?\\n\\n"
            "Los productos existentes y los historiales no se modificarán.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
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

        self.setWindowTitle(
            "Editar producto" if product else "Nuevo producto"
        )

        self.setMinimumWidth(500)

        self._create_widgets()
        self._load_catalogs()

        if product:
            self._load_product(product)
        else:
            self.codigo.setText(
                self.product_service.get_next_internal_code()
            )

    def _create_widgets(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

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

        self.proveedor = QComboBox()
        self.proveedor.setEditable(False)

        form.addRow("Código interno:", self.codigo)
        form.addRow("Código de barras:", self.codigo_barras)
        form.addRow("Código QR:", self.codigo_qr)
        form.addRow("Nombre:", self.nombre)
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
        form.addRow("Costo:", self.costo)
        form.addRow("Precio de venta:", self.precio)
        form.addRow("Existencia:", self.existencia)
        form.addRow("Stock mínimo:", self.stock_minimo)
        form.addRow("Proveedor:", self.proveedor)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    @staticmethod
    def _create_money_spinbox() -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setDecimals(2)
        widget.setMaximum(999999999.99)
        widget.setMinimum(0)
        widget.setSingleStep(1)
        widget.setPrefix("$ ")
        return widget

    @staticmethod
    def _create_quantity_spinbox() -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setDecimals(3)
        widget.setMaximum(999999999.999)
        widget.setMinimum(0)
        widget.setSingleStep(1)
        return widget

    def _manage_categories(self) -> None:
        original_id = self.categoria.currentData()
        CatalogManagerDialog(
            self.product_service, "categorias", parent=self
        ).exec()
        self._load_catalogs()
        index = self.categoria.findData(original_id)
        if index >= 0:
            self.categoria.setCurrentIndex(index)

    def _manage_units(self) -> None:
        original_unit = self.unidad.currentText()
        CatalogManagerDialog(
            self.product_service, "unidades", parent=self
        ).exec()
        self._load_catalogs()
        index = self.unidad.findText(original_unit)
        if index >= 0:
            self.unidad.setCurrentIndex(index)

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

        if self.categoria.currentData() is None or not self.unidad.currentText():
            QMessageBox.warning(self, "Dato faltante",
                "Selecciona una categoría y una unidad válidas.")
            return

        data = {
            "codigo": codigo,
            "codigo_barras": self.codigo_barras.text().strip(),
            "codigo_qr": self.codigo_qr.text().strip(),
            "nombre": nombre,
            "categoria_id": self.categoria.currentData(),
            "marca": self.marca.text().strip(),
            "color": self.color.text().strip(),
            "unidad": self.unidad.currentText(),
            "costo": self.costo.value(),
            "precio": self.precio.value(),
            "existencia": self.existencia.value(),
            "stock_minimo": self.stock_minimo.value(),
            "proveedor_id": self.proveedor.currentData(),
        }

        try:
            if self.product:
                self.product_service.update_product(
                    self.product["id"],
                    data,
                )
            else:
                self.product_service.create_product(data)

        except Exception as error:
            QMessageBox.critical(
                self,
                "No se pudo guardar",
                f"No fue posible guardar el producto.\n\n{error}",
            )
            return

        self.accept()
