from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from app.database.connection import Database
from app.ui.products_window import ProductsWindow
from app.ui.sale_window import SaleWindow
from app.ui.sale_history_window import SaleHistoryWindow
from app.ui.purchase_window import PurchaseWindow
from app.ui.purchase_history_window import PurchaseHistoryWindow
from app.ui.dashboard_window import DashboardWindow
from app.ui.configuration_window import ConfigurationWindow
from app.ui.cash_closing_window import CashClosingWindow

class MainWindow(QMainWindow):
    """Ventana principal de Echando Chal POS."""

    def __init__(self, database: Database) -> None:
        super().__init__()

        self.database = database

        self.setWindowTitle("Echando Chal POS")
        self.resize(1200, 750)
        self.setMinimumSize(1000, 650)

        self.products_window = ProductsWindow(
            self.database,
            self,
        )
        self.purchase_window = PurchaseWindow(
          self.database,
        self,
        )
        self.sale_window = SaleWindow(
            self.database,
            self,
        )
        self.sale_history_window = SaleHistoryWindow(
            self.database,
            self,
        )
        self.purchase_history_window = PurchaseHistoryWindow(
            self.database,
            self,
        )
        self.dashboard_window = DashboardWindow(
            self.database,
            self,
        )
        self.configuration_window = ConfigurationWindow(
            self.database,
            self,
        )
        self.cash_closing_window = CashClosingWindow(
            self.database,
            self,
        )
        self.configuration_window.settings_saved.connect(
            self._apply_settings
        )
        self._crear_interfaz()
        self._apply_settings(
            self.configuration_window.service.get_settings()
        )

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

        self.business_title = QLabel("ECHANDO CHAL")
        self.business_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitulo = QLabel("PUNTO DE VENTA")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.business_title)
        layout.addWidget(subtitulo)
        layout.addSpacing(25)

        botones = [
            ("🛒  Nueva venta", 0),
            ("📦  Productos", 1),
            ("📥  Compras", 2),
            ("📜  Historial de ventas", 3),
            ("📋  Historial de compras", 4),
            ("💰  Corte diario", 5),
            ("📈  Dashboard", 6),
            ("⚙  Configuración", 7),
        ]

        for texto, indice in botones:
            boton = QPushButton(texto)
            boton.setMinimumHeight(45)

            boton.clicked.connect(
                lambda checked=False, i=indice:
                self._mostrar_pagina(i)
            )

            layout.addWidget(boton)

        layout.addStretch()

        version = QLabel(
            "Echando Chal POS\nv0.1.0"
        )

        version.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(version)

        return menu

    def _crear_contenido(self) -> QStackedWidget:
        self.paginas = QStackedWidget()

        pagina_venta = self.sale_window
        pagina_productos = self.products_window
        pagina_compras = self.purchase_window
        pagina_historial = self.sale_history_window
        pagina_historial_compras = self.purchase_history_window
        pagina_corte = self.cash_closing_window
        pagina_dashboard = self.dashboard_window
        pagina_configuracion = self.configuration_window

        for pagina in [
        pagina_venta,
        pagina_productos,
        pagina_compras,
        pagina_historial,
        pagina_historial_compras,
        pagina_corte,
        pagina_dashboard,
        pagina_configuracion,
        ]:
            self.paginas.addWidget(pagina)

        return self.paginas

    @staticmethod
    def _pagina_placeholder(
        nombre: str,
    ) -> QWidget:
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

        return pagina

    def _mostrar_pagina(
        self,
        indice: int,
    ) -> None:
        self.paginas.setCurrentIndex(indice)

        if indice == 0:
            self.sale_window.focus_input()

        elif indice == 1:
            self.products_window._load_products()

        elif indice == 2:
            self.purchase_window.refresh()

        elif indice == 3:
            self.sale_history_window.refresh()
        elif indice == 4:
            self.purchase_history_window.refresh()
        elif indice == 5:
            self.cash_closing_window.refresh()
        elif indice == 6:
            self.dashboard_window.refresh()
        elif indice == 7:
            self.configuration_window.refresh()

    def _apply_settings(self, settings: dict) -> None:
        business_name = settings["nombre_negocio"]
        self.setWindowTitle(f"{business_name} POS")
        if hasattr(self, "business_title"):
            self.business_title.setText(business_name.upper())
