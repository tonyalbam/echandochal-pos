"""Ventana modal de recepción rápida, optimizada para lectores con Enter."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from app.services.quick_stock_service import QuickStockService


class QuickStockDialog(QDialog):
    def __init__(self, database, initial_code: str = "", parent=None):
        super().__init__(parent)
        self.service = QuickStockService(database)
        self.saved = False
        self.setWindowTitle("Recepción rápida de inventario")
        self.setMinimumSize(720, 460)
        layout = QVBoxLayout(self)

        introduction = QLabel(
            "Escanea productos existentes. Cada lectura suma 1 unidad, "
            "incluso si escaneas varias veces el mismo código. "
            "Puedes modificar el total pendiente de cada producto."
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)

        scan_row = QHBoxLayout()
        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText(
            "Escanea código de barras, QR o código interno y pulsa Enter"
        )
        self.scan_input.returnPressed.connect(self._add_scan)
        scan_button = QPushButton("Agregar lectura")
        scan_button.clicked.connect(self._add_scan)
        scan_row.addWidget(self.scan_input, 1)
        scan_row.addWidget(scan_button)
        layout.addLayout(scan_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Código", "Producto", "Color", "Existencia actual", "Agregar unidades"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        self.summary = QLabel("Pendientes: 0 productos, 0 unidades")
        layout.addWidget(self.summary)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancelar sin guardar")
        cancel.clicked.connect(self.reject)
        self.save_button = QPushButton("Confirmar y guardar")
        self.save_button.clicked.connect(self._save)
        self.save_button.setEnabled(False)
        actions.addWidget(cancel)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)

        if initial_code.strip():
            self._add_code(initial_code)
        self.scan_input.setFocus()

    def _add_scan(self) -> None:
        code = self.scan_input.text().strip()
        self.scan_input.clear()
        if code:
            self._add_code(code)
        self.scan_input.setFocus()

    def _add_code(self, code: str) -> None:
        try:
            product = self.service.add_scan(code)
        except ValueError as error:
            QMessageBox.warning(self, "Código no reconocido", str(error))
            return
        self._refresh()
        self.scan_input.setFocus()

    def _refresh(self) -> None:
        self.table.setRowCount(0)
        for row, (product_id, quantity) in enumerate(self.service.pending.items()):
            product = self.service.products[product_id]
            self.table.insertRow(row)
            columns = (
                str(product["codigo"]), str(product["nombre"]),
                str(product.get("color") or "Sin especificar"),
                f"{float(product['existencia']):g}",
            )
            for col, value in enumerate(columns):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)
            quantity_input = QSpinBox()
            quantity_input.setRange(0, self.service.MAX_QUANTITY)
            quantity_input.setValue(quantity)
            quantity_input.valueChanged.connect(
                lambda value, pid=product_id: self._quantity_changed(pid, value)
            )
            self.table.setCellWidget(row, 4, quantity_input)
        self.table.resizeColumnsToContents()
        self.summary.setText(
            f"Pendientes: {len(self.service.pending)} productos, "
            f"{sum(self.service.pending.values())} unidades"
        )
        self.save_button.setEnabled(bool(self.service.pending))

    def _quantity_changed(self, product_id: int, quantity: int) -> None:
        try:
            self.service.set_quantity(product_id, quantity)
        except ValueError as error:
            QMessageBox.warning(self, "Cantidad incorrecta", str(error))
            self._refresh()
            return
        # Mantener el foco de captura; reconstruir la tabla únicamente al
        # quitar una fila, para no interrumpir la edición numérica.
        if quantity == 0:
            self._refresh()
        else:
            self.summary.setText(
                f"Pendientes: {len(self.service.pending)} productos, "
                f"{sum(self.service.pending.values())} unidades"
            )
            self.save_button.setEnabled(True)

    def _save(self) -> None:
        total = sum(self.service.pending.values())
        confirmation = QMessageBox.question(
            self, "Confirmar entrada de inventario",
            f"¿Agregar {total} unidades al inventario de "
            f"{len(self.service.pending)} productos?\n\n"
            "Solo se guardarán al seleccionar Sí.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        try:
            saved = self.service.save()
        except (ValueError, RuntimeError, Exception) as error:
            QMessageBox.critical(
                self, "No se pudo guardar",
                f"No se aplicó la recepción:\n{error}"
            )
            return
        self.saved = True
        QMessageBox.information(
            self, "Inventario actualizado",
            f"Se agregaron {saved} unidades al inventario correctamente."
        )
        self.accept()
