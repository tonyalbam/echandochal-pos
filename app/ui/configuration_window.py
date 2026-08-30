from datetime import datetime
import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import Database
from app.services.configuration_service import ConfigurationService
from app.services.backup_service import BackupService


class ConfigurationWindow(QWidget):
    """Configuración general del punto de venta."""

    settings_saved = Signal(dict)

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.service = ConfigurationService(database)
        self.backup_service = BackupService(database)
        self._create_ui()
        self.refresh()

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 25)
        layout.setSpacing(16)

        title = QLabel("Configuración")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(title)

        description = QLabel(
            "Datos generales utilizados en ventas y reportes del sistema."
        )
        layout.addWidget(description)

        card = QFrame()
        card.setStyleSheet(
            "QFrame { border: 1px solid #d9d9d9; border-radius: 10px; }"
        )
        form = QFormLayout(card)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(16)

        self.business_name = QLineEdit()
        self.business_name.setMaxLength(100)
        form.addRow("Nombre del negocio:", self.business_name)

        self.commission = QDoubleSpinBox()
        self.commission.setRange(0, 100)
        self.commission.setDecimals(2)
        self.commission.setSuffix(" %")
        form.addRow("Comisión de Mercado Libre:", self.commission)

        self.currency = QLineEdit("MXN")
        self.currency.setReadOnly(True)
        form.addRow("Moneda:", self.currency)

        save_button = QPushButton("Guardar configuración")
        save_button.setMinimumSize(180, 42)
        save_button.clicked.connect(self._save)
        form.addRow("", save_button)

        layout.addWidget(card)

        backup_card = QFrame()
        backup_card.setStyleSheet(
            "QFrame { border: 1px solid #d9d9d9; border-radius: 10px; }"
        )
        backup_layout = QVBoxLayout(backup_card)
        backup_layout.setContentsMargins(24, 24, 24, 24)
        backup_layout.setSpacing(12)

        backup_title = QLabel("Respaldo de información")
        backup_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        backup_layout.addWidget(backup_title)
        backup_layout.addWidget(
            QLabel(
                "Crea una copia validada de productos, ventas, compras "
                "y configuración."
            )
        )

        backup_button = QPushButton("Crear respaldo")
        backup_button.setMinimumSize(160, 42)
        backup_button.clicked.connect(self._create_backup)
        backup_layout.addWidget(backup_button)

        restore_button = QPushButton("Restaurar respaldo")
        restore_button.setMinimumSize(160, 42)
        restore_button.clicked.connect(self._restore_backup)
        backup_layout.addWidget(restore_button)

        layout.addWidget(backup_card)
        layout.addStretch()

    def _save(self) -> None:
        try:
            settings = self.service.update_settings(
                self.business_name.text(),
                self.commission.value(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Datos no válidos", str(error))
            return
        except Exception as error:
            QMessageBox.critical(
                self,
                "No se pudo guardar",
                f"No fue posible guardar la configuración:\n{error}",
            )
            return

        self.settings_saved.emit(settings)
        QMessageBox.information(
            self,
            "Configuración guardada",
            "Los cambios se guardaron correctamente.",
        )

    def refresh(self) -> None:
        settings = self.service.get_settings()
        self.business_name.setText(settings["nombre_negocio"])
        self.commission.setValue(settings["comision_mercado_libre"])
        self.currency.setText(settings["moneda"])

    def _create_backup(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_name = f"echandochal_respaldo_{timestamp}.db"

        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Crear respaldo de la base de datos",
            suggested_name,
            "Base de datos SQLite (*.db)",
        )

        if not destination:
            return

        try:
            output_path = self.backup_service.create_backup(destination)
        except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
            QMessageBox.critical(
                self,
                "No se pudo crear el respaldo",
                f"No fue posible crear el respaldo:\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "Respaldo creado",
            (
                "El respaldo se creó y validó correctamente en:\n"
                f"{output_path}"
            ),
        )

    def _restore_backup(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar respaldo para restaurar",
            "",
            "Base de datos SQLite (*.db)",
        )

        if not source:
            return

        try:
            info = self.backup_service.validate_backup(source)
        except (OSError, sqlite3.Error, ValueError) as error:
            QMessageBox.critical(
                self,
                "Respaldo no válido",
                f"El archivo seleccionado no puede restaurarse:\n{error}",
            )
            return

        answer = QMessageBox.warning(
            self,
            "Confirmar restauración",
            (
                "La información actual será sustituida por el respaldo.\n\n"
                f"Productos: {info['productos']}\n"
                f"Ventas: {info['ventas']}\n"
                f"Compras: {info['compras']}\n\n"
                "Antes de continuar se creará automáticamente una copia "
                "de seguridad del estado actual."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.backup_service.restore_backup(source)
        except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
            QMessageBox.critical(
                self,
                "No se pudo restaurar",
                str(error),
            )
            return

        self.refresh()
        settings = self.service.get_settings()
        self.settings_saved.emit(settings)

        QMessageBox.information(
            self,
            "Restauración completada",
            (
                "El respaldo se restauró correctamente.\n\n"
                "Copia automática del estado anterior:\n"
                f"{result['safety_backup']}"
            ),
        )
