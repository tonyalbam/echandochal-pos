import sys

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.database.connection import Database
from app.database.data_location import load_data_directory, installation_directory
from app.ui.data_setup_dialog import DataSetupDialog
from app.database.schema import create_database
from app.services.backup_service import BackupService
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(
        """
        QTableView {
            qproperty-alternatingRowColors: true;
            background-color: palette(window);
            alternate-background-color: rgba(74, 144, 184, 45);
            color: palette(window-text);
            gridline-color: palette(mid);
        }
        QTableView::item:selected {
            background-color: #2F75B5;
            color: #FFFFFF;
        }
        """
    )

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
    window.show()

    exit_code = app.exec()

    database.close()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
