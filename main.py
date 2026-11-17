import sys
from pathlib import Path

from PySide6.QtGui import QIcon

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.database.connection import Database
from app.database.data_location import load_data_directory, installation_directory
from app.ui.data_setup_dialog import DataSetupDialog
from app.database.schema import create_database
from app.services.backup_service import BackupService
from app.ui.main_window import MainWindow
from app.ui.theme import WindowsThemeManager
from app.ui.checkbox_style import AccessibleCheckboxStyle


def main() -> int:
    app = QApplication(sys.argv)
    # Ruta válida tanto para ejecución desde el repositorio como para
    # PyInstaller (main.py se ubica en el directorio de recursos).
    icon_file = Path(__file__).resolve().parent / "app" / "assets" / "echandochal_icon.png"
    if icon_file.is_file():
        app.setWindowIcon(QIcon(str(icon_file)))
    app.setStyle('Fusion')
    # El estilo de casillas se mantiene activo al alternar temas de Windows.
    checkbox_style = AccessibleCheckboxStyle(app.style())
    app.setStyle(checkbox_style)
    theme_manager = WindowsThemeManager(app)

    try:
        configured = load_data_directory()
        if configured is None:
            legacy = installation_directory() / "data" / "echandochal.db"
            wizard = DataSetupDialog(legacy if legacy.is_file() else None)
            if wizard.exec() != QDialog.DialogCode.Accepted:
                return 1
        database = Database()
        create_database(database)
    except Exception as error:
        QMessageBox.critical(
            None, "Error al abrir los datos",
            "No fue posible abrir la base de datos.\n"
            "No se creó una base vacía.\n\n" + str(error),
        )
        return 1

    # Conserva una copia validada al iniciar por primera vez cada día.
    try:
        BackupService(database).create_daily_automatic_backup()
    except Exception as error:
        print(f"Aviso: no se pudo crear el respaldo automático: {error}")

    window = MainWindow(database)
    theme_manager.theme_changed.connect(window.apply_theme)
    window.apply_theme(theme_manager.dark_mode)
    window.setWindowIcon(app.windowIcon())
    window.showMaximized()

    exit_code = app.exec()

    database.close()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
