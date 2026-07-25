from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.services.product_service import ProductService


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

    def _create_widgets(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.codigo = QLineEdit()
        self.codigo.setPlaceholderText("Ej. ECH000001")

        self.codigo_barras = QLineEdit()
        self.codigo_barras.setPlaceholderText(
            "Escanea el código de barras aquí"
        )

        self.nombre = QLineEdit()

        self.categoria = QComboBox()
        self.categoria.setEditable(False)

        self.marca = QLineEdit()
        self.color = QLineEdit()

        self.unidad = QComboBox()
        self.unidad.addItems(
            [
                "pieza",
                "madeja",
                "ovillo",
                "metro",
                "gramo",
                "kilogramo",
                "paquete",
            ]
        )

        self.costo = self._create_money_spinbox()
        self.precio = self._create_money_spinbox()

        self.existencia = self._create_quantity_spinbox()
        self.stock_minimo = self._create_quantity_spinbox()

        self.proveedor = QComboBox()
        self.proveedor.setEditable(False)

        form.addRow("Código interno:", self.codigo)
        form.addRow("Código de barras:", self.codigo_barras)
        form.addRow("Nombre:", self.nombre)
        form.addRow("Categoría:", self.categoria)
        form.addRow("Marca:", self.marca)
        form.addRow("Color:", self.color)
        form.addRow("Unidad:", self.unidad)
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

    def _load_catalogs(self) -> None:
        self.categoria.clear()
        self.categoria.addItem("Sin categoría", None)

        for category in self.product_service.get_categories():
            self.categoria.addItem(
                category["nombre"],
                category["id"],
            )

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
        self.nombre.setText(product["nombre"])
        self.marca.setText(product["marca"] or "")
        self.color.setText(product["color"] or "")

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

            if index >= 0:
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

        data = {
            "codigo": codigo,
            "codigo_barras": self.codigo_barras.text().strip(),
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
