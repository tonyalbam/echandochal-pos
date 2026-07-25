import sys

from PySide6.QtWidgets import QApplication

from app.database.connection import Database
from app.database.schema import create_database
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)

    database = Database()
    create_database(database)

    window = MainWindow(database)
    window.show()

    exit_code = app.exec()

    database.close()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
