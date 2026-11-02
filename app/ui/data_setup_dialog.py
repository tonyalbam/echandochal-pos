"""Asistente de ubicación de datos en el primer inicio."""
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QHBoxLayout, QRadioButton,
)

from app.database.data_location import installation_directory, validate_data_directory
from app.database.data_migration import migrate_existing_database, initialize_new_database


class DataSetupDialog(QDialog):
    def __init__(self, legacy_database: Path | None = None, parent=None):
        super().__init__(parent)
        self.legacy_database = legacy_database
        self.setWindowTitle("Echando Chal POS | Ubicación de datos")
        self.setMinimumWidth(580)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Seleccione una carpeta PERMANENTE para los datos.\n"
            "Debe ser diferente de la carpeta donde se instaló la aplicación.\n"
            "Se conservará para futuras actualizaciones y reinstalaciones."
        ))
        self.folder = QLineEdit()
        self.folder.setPlaceholderText(r"Ejemplo: D:\DatosEchandoChal")
        row = QHBoxLayout()
        row.addWidget(self.folder)
        browse = QPushButton("Examinar...")
        browse.clicked.connect(self.browse)
        row.addWidget(browse)
        layout.addLayout(row)
        self.migrate = QRadioButton("Conservar y migrar la base de datos existente")
        self.fresh = QRadioButton("Crear una base nueva (solo primera instalación)")
        layout.addWidget(self.migrate)
        layout.addWidget(self.fresh)
        if legacy_database and legacy_database.is_file():
            self.migrate.setChecked(True)
            layout.addWidget(QLabel(f"Base existente detectada:\n{legacy_database}"))
        else:
            self.migrate.setEnabled(False)
            self.fresh.setChecked(True)
            layout.addWidget(QLabel(
                "No se detectó una base anterior en esta instalación.\n"
                "Si ya utilizaba el sistema, cancele y localice su base antes de continuar."
            ))
        actions = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("Continuar")
        confirm.clicked.connect(self.apply)
        actions.addWidget(cancel)
        actions.addWidget(confirm)
        layout.addLayout(actions)

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Carpeta de datos")
        if folder:
            self.folder.setText(folder)

    def apply(self):
        try:
            folder = validate_data_directory(self.folder.text().strip())
            if self.migrate.isChecked():
                if not self.legacy_database:
                    raise RuntimeError("No se detectó una base para migrar.")
                if QMessageBox.question(
                    self, "Confirmar migración",
                    "Se copiará la base existente a la carpeta elegida.\n"
                    "El original se conservará sin modificaciones. ¿Continuar?"
                ) != QMessageBox.StandardButton.Yes:
                    return
                migrate_existing_database(self.legacy_database, folder)
            else:
                if QMessageBox.question(
                    self, "Confirmar base nueva",
                    "Se creará una base VACÍA. Si ya tiene ventas o productos, "
                    "cancele y recupere su base anterior. ¿Continuar?"
                ) != QMessageBox.StandardButton.Yes:
                    return
                initialize_new_database(folder)
        except Exception as error:
            QMessageBox.critical(self, "No se completó la configuración", str(error))
            return
        self.accept()
