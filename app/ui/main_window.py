from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import Database


class MainWindow(QMainWindow):
    """Ventana principal de Echando Chal POS."""

    def __init__(self, database: Database) -> None:
        super().__init__()

        self.database = database

        self.setWindowTitle("Echando Chal POS")
        self.resize(1200, 750)
        self.setMinimumSize(1000, 650)

        self._crear_interfaz()

    def _crear_interfaz(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout_principal = QHBoxLayout(central)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        menu = self._crear_menu()
        contenido = self._crear_contenido()

        layout_principal.addWidget(menu)
        layout_principal.addWidget(contenido, 1)

    def _crear_menu(self) -> QFrame:
        menu = QFrame()
        menu.setFixedWidth(230)

        layout = QVBoxLayout(menu)
        layout.setContentsMargins(20, 25, 20, 20)
        layout.setSpacing(10)

        titulo = QLabel("ECHANDO CHAL")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitulo = QLabel("PUNTO DE VENTA")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(25)

        botones = [
            ("🛒  Nueva venta", 0),
            ("📦  Productos", 1),
            ("📥  Compras", 2),
            ("📊  Reportes", 3),
            ("📈  Dashboard", 4),
            ("⚙  Configuración", 5),
        ]

        for texto, indice in botones:
            boton = QPushButton(texto)
            boton.setMinimumHeight(45)
            boton.clicked.connect(
                lambda checked=False, i=indice: self._mostrar_pagina(i)
            )
            layout.addWidget(boton)

        layout.addStretch()

        version = QLabel("Echando Chal POS\nv0.1.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(version)

        return menu

    def _crear_contenido(self) -> QWidget:
        self.paginas = QStackedWidget()

        paginas = [
            "Nueva Venta",
            "Productos",
            "Compras",
            "Reportes",
            "Dashboard",
            "Configuración",
        ]

        for nombre in paginas:
            pagina = QWidget()
            layout = QVBoxLayout(pagina)

            titulo = QLabel(nombre)
            titulo.setStyleSheet(
                """
                font-size: 28px;
                font-weight: bold;
                """
            )

            layout.addWidget(titulo)
            layout.addStretch()

            self.paginas.addWidget(pagina)

        return self.paginas

    def _mostrar_pagina(self, indice: int) -> None:
        self.paginas.setCurrentIndex(indice)
