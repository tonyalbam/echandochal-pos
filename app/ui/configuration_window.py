from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
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


class ConfigurationWindow(QWidget):
    """Configuración general del punto de venta."""

    settings_saved = Signal(dict)

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.service = ConfigurationService(database)
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
