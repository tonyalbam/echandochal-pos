from PySide6.QtCore import QTimer, Signal, QStringListModel, Qt
from PySide6.QtWidgets import (
    QCompleter,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import Database
from app.services.purchase_service import PurchaseService


class ClearOnFocusLineEdit(QLineEdit):
    """Limpia la búsqueda anterior al comenzar otra captura."""

    def focusInEvent(self, event) -> None:
        self.clear()
        super().focusInEvent(event)


class PurchaseItemsTable(QTableWidget):
    """Grid de compra con eliminación rápida mediante D."""

    delete_requested = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_D:
            self.delete_requested.emit()
            return
        super().keyPressEvent(event)


class PurchaseWindow(QWidget):
    """Ventana para registrar compras de mercancía."""

    def __init__(
        self,
        database: Database,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.database = database
        self.service = PurchaseService(database)

        self.items: list[dict] = []
        self.suggestion_products: dict[str, dict] = {}
        self.ignore_next_return = False

        self._create_ui()
        self._load_suppliers()

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            25,
            20,
            25,
            25,
        )

        layout.setSpacing(12)

        title = QLabel("Nueva compra")

        title.setStyleSheet(
            """
            font-size: 28px;
            font-weight: bold;
            """
        )

        layout.addWidget(title)

        # Proveedor
        supplier_layout = QHBoxLayout()

        supplier_layout.addWidget(
            QLabel("Proveedor:")
        )

        self.supplier = QComboBox()

        self.supplier.setMinimumWidth(300)

        supplier_layout.addWidget(
            self.supplier
        )

        supplier_layout.addStretch()

        layout.addLayout(
            supplier_layout
        )

        # Búsqueda de producto
        product_layout = QHBoxLayout()

        product_layout.addWidget(
            QLabel("Producto:")
        )

        self.product_search = ClearOnFocusLineEdit()

        self.product_search.setPlaceholderText(
            "Código, código de barras, nombre o marca..."
        )

        self.product_search.returnPressed.connect(
            self._add_product
        )
        self.suggestion_model = QStringListModel(self)
        self.completer = QCompleter(self.suggestion_model, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(
            QCompleter.CompletionMode.UnfilteredPopupCompletion
        )
        self.completer.setMaxVisibleItems(12)
        self.completer.activated.connect(self._add_suggestion)
        self.product_search.setCompleter(self.completer)
        self.product_search.textEdited.connect(self._update_suggestions)

        product_layout.addWidget(
            self.product_search,
            1,
        )

        add_button = QPushButton(
            "Agregar"
        )

        add_button.clicked.connect(
            self._add_product
        )

        product_layout.addWidget(
            add_button
        )

        layout.addLayout(
            product_layout
        )

        # Tabla de productos
        self.table = PurchaseItemsTable(
            0,
            8,
        )

        self.table.setHorizontalHeaderLabels(
            [
                "Código",
                "Producto",
                "Marca",
                "Color",
                "Categoría",
                "Cantidad",
                "Costo unitario",
                "Subtotal",
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
        self.table.delete_requested.connect(self._remove_selected_line)

        self.table.horizontalHeader().setStretchLastSection(
            True
        )

        layout.addWidget(
            self.table,
            1,
        )

        # Controles de línea
        line_layout = QHBoxLayout()

        line_layout.addWidget(
            QLabel("Cantidad:")
        )

        self.quantity = QSpinBox()

        self.quantity.setRange(
            1,
            999999,
        )

        self.quantity.setValue(1)

        line_layout.addWidget(
            self.quantity
        )

        line_layout.addWidget(
            QLabel("Costo unitario:")
        )

        self.unit_cost = QDoubleSpinBox()

        self.unit_cost.setRange(
            0,
            999999999.99,
        )

        self.unit_cost.setDecimals(2)

        self.unit_cost.setPrefix(
            "$ "
        )

        line_layout.addWidget(
            self.unit_cost
        )

        update_button = QPushButton(
            "Actualizar línea"
        )

        update_button.clicked.connect(
            self._update_selected_line
        )

        line_layout.addWidget(
            update_button
        )

        remove_button = QPushButton(
            "Eliminar línea"
        )

        remove_button.clicked.connect(
            self._remove_selected_line
        )

        line_layout.addWidget(
            remove_button
        )

        line_layout.addStretch()

        layout.addLayout(
            line_layout
        )

        # Notas
        notes_layout = QHBoxLayout()

        notes_layout.addWidget(
            QLabel("Notas:")
        )

        self.notes = QLineEdit()

        self.notes.setPlaceholderText(
            "Notas opcionales de la compra..."
        )

        notes_layout.addWidget(
            self.notes,
            1,
        )

        layout.addLayout(
            notes_layout
        )

        # Total
        bottom_layout = QHBoxLayout()

        self.total_label = QLabel(
            "Total: $ 0.00"
        )

        self.total_label.setStyleSheet(
            """
            font-size: 20px;
            font-weight: bold;
            """
        )

        bottom_layout.addWidget(
            self.total_label
        )

        bottom_layout.addStretch()

        clear_button = QPushButton(
            "Limpiar"
        )

        clear_button.clicked.connect(
            self._clear_form
        )

        bottom_layout.addWidget(
            clear_button
        )

        save_button = QPushButton(
            "Registrar compra"
        )

        save_button.setMinimumSize(
            160,
            42,
        )

        save_button.clicked.connect(
            self._save_purchase
        )

        bottom_layout.addWidget(
            save_button
        )

        layout.addLayout(
            bottom_layout
        )

    def _load_suppliers(self) -> None:
        self.supplier.clear()

        self.supplier.addItem(
            "Sin proveedor",
            None,
        )

        cursor = self.database.cursor()

        cursor.execute(
            """
            SELECT
                id,
                nombre
            FROM proveedores
            WHERE activo = 1
            ORDER BY nombre
            """
        )

        for row in cursor.fetchall():
            self.supplier.addItem(
                row["nombre"],
                row["id"],
            )

    def _add_product(self) -> None:
        if self.ignore_next_return:
            self.ignore_next_return = False
            self.product_search.clear()
            return

        query = self.product_search.text().strip()
        product = self.service.find_product(query)
        if product is None:
            matches = self.service.search_products(query)
            product = matches[0] if matches else None

        if product is None:
            QMessageBox.warning(
                self,
                "Producto no encontrado",
                "No se encontró un producto activo que coincida con la "
                "búsqueda.",
            )
            return

        self._append_product(product)

    def _update_suggestions(self, text: str) -> None:
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

    def _add_suggestion(self, label: str) -> None:
        product = self.suggestion_products.get(label)
        if product:
            self.ignore_next_return = True
            self._append_product(product)
            QTimer.singleShot(0, self._reset_return_guard)

    def _reset_return_guard(self) -> None:
        self.ignore_next_return = False

    def _append_product(self, product: dict) -> None:

        for index, item in enumerate(
            self.items
        ):
            if item["producto_id"] == product["id"]:
                self.table.selectRow(index)
                self.quantity.setValue(
                    item["cantidad"]
                )
                self.unit_cost.setValue(
                    item["costo_unitario"]
                )
                self.product_search.clear()
                return

        cost = float(
            product["costo"] or 0
        )

        item = {
            "producto_id": product["id"],
            "codigo": product["codigo"],
            "nombre": product["nombre"],
            "marca": product["marca"],
            "color": product["color"],
            "categoria": product["categoria"],
            "cantidad": 1,
            "costo_unitario": cost,
        }

        self.items.append(item)

        self._refresh_table()

        row = len(self.items) - 1

        self.table.selectRow(row)

        self.quantity.setValue(
            item["cantidad"]
        )

        self.unit_cost.setValue(
            item["costo_unitario"]
        )

        self.product_search.clear()

    def _selected_row(self) -> int:
        return self.table.currentRow()

    def _update_selected_line(self) -> None:
        row = self._selected_row()

        if row < 0 or row >= len(self.items):
            QMessageBox.information(
                self,
                "Selecciona un producto",
                "Selecciona primero una línea de la compra.",
            )
            return

        self.items[row]["cantidad"] = int(self.quantity.value())

        self.items[row]["costo_unitario"] = float(
            self.unit_cost.value()
        )

        self._refresh_table()

        self.table.selectRow(row)

    def _remove_selected_line(self) -> None:
        row = self._selected_row()

        if row < 0 or row >= len(self.items):
            QMessageBox.information(
                self,
                "Selecciona un producto",
                "Selecciona primero una línea de la compra.",
            )
            return

        self.items.pop(row)

        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)

        total = 0.0

        for row, item in enumerate(
            self.items
        ):
            self.table.insertRow(row)

            quantity = float(
                item["cantidad"]
            )

            unit_cost = float(
                item["costo_unitario"]
            )

            subtotal = round(
                quantity * unit_cost,
                2,
            )

            total += subtotal

            values = [
                item["codigo"],
                item["nombre"],
                item["marca"],
                item["color"],
                item["categoria"],
                "",
                f"$ {unit_cost:,.2f}",
                f"$ {subtotal:,.2f}",
            ]

            for column, value in enumerate(
                values
            ):
                table_item = QTableWidgetItem(
                    str(value)
                )

                if column >= 5:
                    table_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )

                self.table.setItem(
                    row,
                    column,
                    table_item,
                )

            quantity_input = QSpinBox()
            quantity_input.setRange(1, 999999)
            quantity_input.setValue(int(quantity))
            quantity_input.valueChanged.connect(
                lambda value, index=row: self._change_row_quantity(index, value)
            )
            self.table.setCellWidget(row, 5, quantity_input)

        self.table.resizeColumnsToContents()

        self.total_label.setText(
            f"Total: $ {total:,.2f}"
        )

    def _change_row_quantity(self, row: int, quantity: int) -> None:
        if not 0 <= row < len(self.items):
            return
        self.items[row]["cantidad"] = int(quantity)
        subtotal = round(
            quantity * float(self.items[row]["costo_unitario"]), 2
        )
        subtotal_item = self.table.item(row, 7)
        if subtotal_item is not None:
            subtotal_item.setText(f"$ {subtotal:,.2f}")
        total = sum(
            int(item["cantidad"]) * float(item["costo_unitario"])
            for item in self.items
        )
        self.total_label.setText(f"Total: $ {total:,.2f}")

    def _save_purchase(self) -> None:
        if not self.items:
            QMessageBox.warning(
                self,
                "Compra vacía",
                "Agrega al menos un producto antes de registrar la compra.",
            )
            return

        supplier_id = self.supplier.currentData()
        if supplier_id is None or self.supplier.currentText() == "Sin proveedor":
            QMessageBox.warning(
                self,
                "Proveedor requerido",
                "Debes seleccionar un proveedor para registrar la compra.",
            )
            self.supplier.setFocus()
            return

        items = [
            {
                "producto_id": item["producto_id"],
                "cantidad": item["cantidad"],
                "costo_unitario": item["costo_unitario"],
            }
            for item in self.items
        ]

        total = sum(
            float(item["cantidad"])
            * float(item["costo_unitario"])
            for item in items
        )

        answer = QMessageBox.question(
            self,
            "Registrar compra",
            (
                "¿Deseas registrar esta compra?\n\n"
                f"Total: $ {total:,.2f}"
            ),
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.service.create_purchase(
                items=items,
                supplier_id=supplier_id,
                notes=self.notes.text().strip(),
                user_id=None,
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Error al registrar compra",
                str(error),
            )
            return

        QMessageBox.information(
            self,
            "Compra registrada",
            (
                "La compra se registró correctamente.\n\n"
                f"Folio: {result['folio']}\n"
                f"Total: $ {result['total']:,.2f}"
            ),
        )

        self._clear_form()

    def _clear_form(self) -> None:
        self.items.clear()

        self.product_search.clear()

        self.quantity.setValue(1)

        self.unit_cost.setValue(0)

        self.notes.clear()

        if self.supplier.count() > 0:
            self.supplier.setCurrentIndex(0)

        self._refresh_table()

    def refresh(self) -> None:
        self._load_suppliers()
