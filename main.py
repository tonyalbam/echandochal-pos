import sys

from PySide6.QtWidgets import QApplication

from app.database.connection import Database
from app.database.schema import create_database
from app.services.backup_service import BackupService
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(
        """
        QTableView {
            qproperty-alternatingRowColors: true;
            alternate-background-color: #F2F7FB;
            background-color: #FFFFFF;
        }
        """
    )

    database = Database()
    create_database(database)

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
