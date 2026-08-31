from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from app.database.connection import Database
from app.services.supplier_service import SupplierService


class SupplierDialog(QDialog):
    def __init__(self, service: SupplierService, supplier=None, parent=None):
        super().__init__(parent)
        self.service = service
        self.supplier = supplier
        self.setWindowTitle("Editar proveedor" if supplier else "Nuevo proveedor")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.address = QLineEdit()
        self.phone = QLineEdit()
        form.addRow("Nombre:", self.name)
        form.addRow("Dirección:", self.address)
        form.addRow("Teléfono:", self.phone)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if supplier:
            self.name.setText(supplier["nombre"])
            self.address.setText(supplier["direccion"])
            self.phone.setText(supplier["telefono"])

    def _save(self) -> None:
        try:
            self.service.save_supplier(
                self.name.text(), self.address.text(), self.phone.text(),
                self.supplier["id"] if self.supplier else None,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Datos no válidos", str(error))
            return
        self.accept()


class SupplierWindow(QWidget):
    """Catálogo de proveedores."""

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.service = SupplierService(database)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 25)
        header = QHBoxLayout()
        title = QLabel("Proveedores")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        new_button = QPushButton("＋ Nuevo proveedor")
        new_button.clicked.connect(self._new)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(new_button)
        layout.addLayout(header)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, dirección o teléfono...")
        self.search.textChanged.connect(self.refresh)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Nombre", "Dirección", "Teléfono"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        edit_button = QPushButton("Editar")
        edit_button.clicked.connect(self._edit)
        deactivate_button = QPushButton("Desactivar")
        deactivate_button.clicked.connect(self._deactivate)
        buttons.addWidget(edit_button)
        buttons.addWidget(deactivate_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self) -> None:
        suppliers = self.service.list_suppliers(self.search.text())
        self.table.setRowCount(0)
        for row, supplier in enumerate(suppliers):
            self.table.insertRow(row)
            for column, key in enumerate(("nombre", "direccion", "telefono")):
                self.table.setItem(row, column, QTableWidgetItem(supplier[key]))
            self.table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole, supplier["id"]
            )
        self.table.resizeColumnsToContents()

    def _selected(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return None
        return self.service.get_supplier(
            int(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        )

    def _new(self) -> None:
        if SupplierDialog(self.service, parent=self).exec():
            self.refresh()

    def _edit(self) -> None:
        supplier = self._selected()
        if supplier is None:
            QMessageBox.information(
                self, "Selecciona un proveedor", "Selecciona el proveedor a editar."
            )
            return
        if SupplierDialog(self.service, supplier, self).exec():
            self.refresh()

    def _deactivate(self) -> None:
        supplier = self._selected()
        if supplier is None:
            QMessageBox.information(
                self, "Selecciona un proveedor", "Selecciona el proveedor a desactivar."
            )
            return
        answer = QMessageBox.question(
            self, "Desactivar proveedor",
            f"¿Deseas desactivar a {supplier['nombre']}?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.service.deactivate_supplier(supplier["id"])
            self.refresh()
