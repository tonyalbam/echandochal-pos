from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QScrollArea,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import Database
from app.services.product_service import ProductService
from app.services.label_service import LabelService
from app.ui.product_dialog import ProductDialog


class ClearOnFocusLineEdit(QLineEdit):
    """Limpia la búsqueda anterior al iniciar una nueva consulta."""

    def focusInEvent(self, event) -> None:
        self.clear()
        super().focusInEvent(event)


class BatchLabelDialog(QDialog):
    """Selector independiente: no afecta la selección para editar productos."""

    def __init__(self, products: list[dict], selected_ids: set[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generar etiquetas de varios productos")
        self.resize(640, 570)
        layout = QVBoxLayout(self)
        help_label = QLabel(
            "Selecciona uno o varios productos. Puedes buscar por nombre, "
            "código, marca o color. La exportación no modifica el inventario."
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrar productos para seleccionar...")
        layout.addWidget(self.search)
        buttons = QHBoxLayout()
        all_visible = QPushButton("Marcar visibles")
        clear_visible = QPushButton("Desmarcar visibles")
        buttons.addWidget(all_visible)
        buttons.addWidget(clear_visible)
        layout.addLayout(buttons)

        self.product_checks: list[tuple[dict, QCheckBox]] = []
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        for product in products:
            label = (
                f"{product['codigo']} | {product['nombre']} | "
                f"Color: {product.get('color') or 'Sin especificar'}"
            )
            checkbox = QCheckBox(label)
            checkbox.setChecked(product["id"] in selected_ids)
            content_layout.addWidget(checkbox)
            self.product_checks.append((product, checkbox))
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.search.textChanged.connect(self._filter)
        all_visible.clicked.connect(lambda: self._toggle_visible(True))
        clear_visible.clicked.connect(lambda: self._toggle_visible(False))

        content_row = QHBoxLayout()
        content_row.addWidget(QLabel("Contenido:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(LabelService.FORMATS)
        self.format_combo.setCurrentText("Ambos")
        content_row.addWidget(self.format_combo, 1)
        layout.addLayout(content_row)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Archivo:"))
        self.output_combo = QComboBox()
        self.output_combo.addItems(LabelService.OUTPUT_TYPES)
        output_row.addWidget(self.output_combo, 1)
        layout.addLayout(output_row)

        self.selection_count = QLabel()
        layout.addWidget(self.selection_count)
        for _, checkbox in self.product_checks:
            checkbox.toggled.connect(self._update_count)
        self._update_count()
        controls = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        controls.button(QDialogButtonBox.StandardButton.Ok).setText("Generar archivo")
        controls.accepted.connect(self._accept_selection)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)

    def _filter(self, query: str) -> None:
        terms = query.casefold().split()
        for product, checkbox in self.product_checks:
            text = " ".join(str(product.get(field) or "") for field in
                            ("codigo", "nombre", "marca", "color")).casefold()
            checkbox.setVisible(all(term in text for term in terms))

    def _toggle_visible(self, checked: bool) -> None:
        for _, checkbox in self.product_checks:
            if not checkbox.isHidden():
                checkbox.setChecked(checked)

    def _update_count(self, _checked=None) -> None:
        self.selection_count.setText(
            f"Productos seleccionados: {len(self.product_ids)}"
        )

    @property
    def product_ids(self) -> list[int]:
        return [int(product["id"]) for product, checkbox in self.product_checks
                if checkbox.isChecked()]

    def _accept_selection(self) -> None:
        if not self.product_ids:
            QMessageBox.information(self, "Sin productos",
                "Selecciona al menos un producto para generar etiquetas.")
            return
        self.accept()


class ProductsWindow(QWidget):
    """Catálogo principal de productos."""

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)

        self.database = database
        self.service = ProductService(database)
        self.label_service = LabelService(database)

        self._create_ui()
        self._load_products()

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()

        title = QLabel("Productos")
        title.setStyleSheet(
            """
            font-size: 28px;
            font-weight: bold;
            """
        )

        header.addWidget(title)
        header.addStretch()

        self.new_button = QPushButton("＋ Nuevo producto")
        self.new_button.clicked.connect(self._new_product)

        self.export_button = QPushButton("Exportar inventario")
        self.export_button.clicked.connect(self._export_inventory)

        header.addWidget(self.export_button)
        header.addWidget(self.new_button)

        layout.addLayout(header)

        search_layout = QHBoxLayout()

        search_label = QLabel("Buscar:")
        self.search = ClearOnFocusLineEdit()
        self.search.setPlaceholderText(
            "Nombre, código interno, código de barras o QR..."
        )
        self.search.textChanged.connect(self._load_products)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search)

        layout.addLayout(search_layout)

        self.table = QTableWidget()

        self.table.setColumnCount(13)

        self.table.setHorizontalHeaderLabels(
            [
                "Código",
                "Código de barras",
                "Código QR",
                "Producto",
                "Categoría",
                "Marca",
                "Color",
                "Unidad",
                "Costo",
                "Precio de venta",
                "Existencia",
                "Stock mínimo",
                "Estado",
            ]
        )

        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.table.doubleClicked.connect(self._edit_selected)
        self.delete_shortcut_products = QShortcut(
            QKeySequence(Qt.Key.Key_Delete), self.table
        )
        self.delete_shortcut_products.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.delete_shortcut_products.activated.connect(self._delete_selected)

        self.table.horizontalHeader().setStretchLastSection(True)

        self.low_stock_table = QTableWidget()
        self.low_stock_table.setColumnCount(9)
        self.low_stock_table.setHorizontalHeaderLabels(
            [
                "Código",
                "Producto",
                "Marca",
                "Color",
                "Categoría",
                "Existencia",
                "Stock mínimo",
                "Faltante al mínimo",
                "Proveedor",
            ]
        )
        self.low_stock_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.low_stock_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.low_stock_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.low_stock_table.doubleClicked.connect(self._edit_selected)
        self.delete_shortcut_low_stock = QShortcut(
            QKeySequence(Qt.Key.Key_Delete), self.low_stock_table
        )
        self.delete_shortcut_low_stock.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.delete_shortcut_low_stock.activated.connect(self._delete_selected)
        self.low_stock_table.horizontalHeader().setStretchLastSection(True)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.table, "Todos los productos")
        self.tabs.addTab(self.low_stock_table, "Stock bajo / agotado")
        layout.addWidget(self.tabs)

        buttons = QHBoxLayout()

        edit_button = QPushButton("Editar")
        edit_button.clicked.connect(self._edit_selected)

        deactivate_button = QPushButton("Desactivar")
        deactivate_button.clicked.connect(self._deactivate_selected)

        delete_button = QPushButton("Eliminar")
        delete_button.setToolTip(
            "Retira el producto del catálogo sin borrar ventas o compras históricas (Supr)."
        )
        delete_button.clicked.connect(self._delete_selected)

        label_button = QPushButton("Generar etiqueta")
        label_button.clicked.connect(self._generate_label)

        buttons.addWidget(edit_button)
        buttons.addWidget(deactivate_button)
        buttons.addWidget(delete_button)
        buttons.addWidget(label_button)
        buttons.addStretch()

        layout.addLayout(buttons)

    def _load_products(self) -> None:
        products = self.service.list_products(
            self.search.text(),
            include_inactive=True,
        )

        self.table.setRowCount(0)

        for row, product in enumerate(products):
            self.table.insertRow(row)

            values = [
                product["codigo"],
                product["codigo_barras"] or "",
                product["codigo_qr"] or "",
                product["nombre"],
                product["categoria"],
                product["marca"],
                product["color"],
                product["unidad"],
                f'$ {product["costo"]:,.2f}',
                f'$ {product["precio"]:,.2f}',
                f'{product["existencia"]:,.3f}',
                f'{product["stock_minimo"]:,.3f}',
                self._stock_status(product),
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))

                if column in (8, 9, 10, 11):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )

                if not product["activo"]:
                    item.setBackground(QColor("#F1666D"))

                self.table.setItem(row, column, item)

            self.table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                product["id"],
            )

        self.table.resizeColumnsToContents()
        self._load_low_stock_products()

    def _load_low_stock_products(self) -> None:
        products = self.service.list_low_stock_products(self.search.text())
        self.low_stock_table.setRowCount(0)

        for row, product in enumerate(products):
            self.low_stock_table.insertRow(row)
            values = [
                product["codigo"],
                product["nombre"],
                product["marca"],
                product["color"],
                product["categoria"],
                f'{product["existencia"]:,.3f}',
                f'{product["stock_minimo"]:,.3f}',
                f'{product["faltante_minimo"]:,.3f}',
                product["proveedor"],
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column in (5, 6, 7):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                self.low_stock_table.setItem(row, column, item)
            self.low_stock_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                product["id"],
            )

        self.low_stock_table.resizeColumnsToContents()

    @staticmethod
    def _stock_status(product: dict) -> str:
        return ProductService.product_status(product)

    def _selected_product_id(self):
        table = (
            self.low_stock_table
            if self.tabs.currentWidget() is self.low_stock_table
            else self.table
        )
        row = table.currentRow()

        if row < 0:
            return None

        item = table.item(row, 0)

        if item is None:
            return None

        return item.data(Qt.ItemDataRole.UserRole)

    def _new_product(self) -> None:
        dialog = ProductDialog(
            self.service,
            parent=self,
        )

        if dialog.exec():
            self._load_products()

    def _edit_selected(self) -> None:
        product_id = self._selected_product_id()

        if product_id is None:
            QMessageBox.information(
                self,
                "Selecciona un producto",
                "Selecciona primero el producto que deseas editar.",
            )
            return

        product = self.service.get_product(product_id)

        if not product:
            QMessageBox.warning(
                self,
                "Producto no encontrado",
                "El producto ya no existe.",
            )
            self._load_products()
            return

        dialog = ProductDialog(
            self.service,
            product=product,
            parent=self,
        )

        if dialog.exec():
            self._load_products()

    def _deactivate_selected(self) -> None:
        product_id = self._selected_product_id()

        if product_id is None:
            QMessageBox.information(
                self,
                "Selecciona un producto",
                "Selecciona primero el producto que deseas desactivar.",
            )
            return

        product = self.service.get_product(product_id)

        if not product:
            return

        answer = QMessageBox.question(
            self,
            "Desactivar producto",
            (
                f"¿Deseas desactivar el producto\n\n"
                f"{product['nombre']}?"
            ),
        )

        if answer == QMessageBox.StandardButton.Yes:
            self.service.deactivate_product(product_id)
            self._load_products()

    def _delete_selected(self) -> None:
        product_id = self._selected_product_id()
        if product_id is None:
            QMessageBox.information(
                self, "Selecciona un producto",
                "Selecciona la fila del producto que deseas eliminar."
            )
            return

        product = self.service.get_product(product_id)
        if product is None or product.get("eliminado", 0):
            QMessageBox.warning(
                self, "Producto no disponible",
                "El producto ya no está disponible en el catálogo."
            )
            self._load_products()
            return

        message = (
            "¿Eliminar del catálogo el producto?\n\n"
            f"{product['codigo']} | {product['nombre']}\n\n"
            "Ya no aparecerá en Productos ni podrá utilizarse "
            "en nuevas ventas o compras.\n\n"
            "Se conservarán las ventas, compras y movimientos históricos.\n"
            "Esta acción no se puede deshacer desde la interfaz."
        )

        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setWindowTitle("Confirmar eliminación de producto")
        confirm.setText(message)
        if float(product.get("existencia") or 0) != 0:
            confirm.setInformativeText(
                f"Atención: tiene una existencia de "
                f"{float(product['existencia']):g} unidades. "
                "Dejará de contabilizarse como inventario activo."
            )

        confirm.setStyleSheet("QLabel { min-width: 420px; }")
        yes_button = confirm.addButton(
            "Sí, eliminar", QMessageBox.ButtonRole.YesRole
        )
        no_button = confirm.addButton(
            "No, cancelar", QMessageBox.ButtonRole.NoRole
        )
        confirm.setDefaultButton(no_button)
        confirm.setEscapeButton(no_button)
        confirm.exec()
        if confirm.clickedButton() is not yes_button:
            return

        try:
            self.service.delete_product(product_id)
        except (ValueError, RuntimeError, OSError) as error:
            QMessageBox.critical(self, "No se pudo eliminar", str(error))
            return
        self._load_products()
        QMessageBox.information(
            self, "Producto eliminado",
            "El producto se retiró del catálogo. Su historial se conserva."
        )

    def _export_inventory(self) -> None:
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar reporte de inventario",
            "reporte_inventario.xlsx",
            "Archivos de Excel (*.xlsx)",
        )

        if not destination:
            return

        try:
            output_path = self.service.export_inventory_report(
                destination,
                search=self.search.text(),
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

    def _generate_label(self) -> None:
        # Todos los productos, incluso si hay un filtro de búsqueda activo.
        products = self.service.list_products(include_inactive=True)
        selected_id = self._selected_product_id()
        dialog = BatchLabelDialog(
            products, {int(selected_id)} if selected_id is not None else set(), self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        output_type = dialog.output_combo.currentText()
        extension = ".pdf" if output_type == "PDF" else ".docx"
        filters = (
            "Documento PDF (*.pdf)" if output_type == "PDF"
            else "Documento Word (*.docx)"
        )
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar etiquetas de productos",
            "etiquetas_productos" + extension,
            filters,
        )
        if not destination:
            return
        try:
            output_path = self.label_service.generate_product_labels(
                dialog.product_ids, destination,
                dialog.format_combo.currentText(), output_type,
            )
        except (OSError, ValueError, ImportError) as error:
            QMessageBox.critical(self, "No se pudo generar", str(error))
            return
        QMessageBox.information(
            self,
            "Etiquetas generadas",
            f"Se generaron {len(dialog.product_ids)} etiquetas en:\\n{output_path}",
        )
