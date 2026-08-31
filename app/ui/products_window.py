from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
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
from app.services.product_service import ProductService
from app.services.label_service import LabelService
from app.ui.product_dialog import ProductDialog


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
        self.search = QLineEdit()
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

        self.table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.table)

        buttons = QHBoxLayout()

        edit_button = QPushButton("Editar")
        edit_button.clicked.connect(self._edit_selected)

        deactivate_button = QPushButton("Desactivar")
        deactivate_button.clicked.connect(self._deactivate_selected)

        label_button = QPushButton("Generar etiqueta")
        label_button.clicked.connect(self._generate_label)

        buttons.addWidget(edit_button)
        buttons.addWidget(deactivate_button)
        buttons.addWidget(label_button)
        buttons.addStretch()

        layout.addLayout(buttons)

    def _load_products(self) -> None:
        products = self.service.list_products(
            self.search.text()
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

                self.table.setItem(row, column, item)

            self.table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                product["id"],
            )

        self.table.resizeColumnsToContents()

    @staticmethod
    def _stock_status(product: dict) -> str:
        if product["existencia"] <= 0:
            return "AGOTADO"

        if product["existencia"] <= product["stock_minimo"]:
            return "BAJO"

        return "OK"

    def _selected_product_id(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(row, 0)

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
        product_id = self._selected_product_id()
        if product_id is None:
            QMessageBox.information(
                self,
                "Selecciona un producto",
                "Selecciona el producto para generar su etiqueta.",
            )
            return

        format_name, accepted = QInputDialog.getItem(
            self,
            "Formato de etiqueta",
            "Contenido:",
            LabelService.FORMATS,
            2,
            False,
        )
        if not accepted:
            return

        product = self.service.get_product(product_id)
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar etiqueta",
            f"etiqueta_{product['codigo']}.pdf",
            "Documento PDF (*.pdf)",
        )
        if not destination:
            return
        try:
            output_path = self.label_service.generate_product_label(
                product_id, destination, format_name
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "No se pudo generar", str(error))
            return
        QMessageBox.information(
            self,
            "Etiqueta generada",
            f"La etiqueta se guardó correctamente en:\n{output_path}",
        )
