from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import Database
from app.services.dashboard_service import DashboardService
from datetime import datetime
from app.ui.widgets.annual_financial_chart import AnnualFinancialChart
from app.ui.widgets.annual_commission_chart import AnnualCommissionChart

class StatCard(QFrame):
    """Tarjeta reutilizable para mostrar un indicador del Dashboard."""

    def __init__(
        self,
        title: str,
        value: str = "$0.00",
        subtitle: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("statCard")
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("cardValue")

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("cardSubtitle")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)
        layout.addStretch()

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.setText(text)


class DashboardWindow(QWidget):
    """Pantalla principal de indicadores financieros y operativos."""

    def __init__(
        self,
        database: Database,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.database = database
        self.service = DashboardService(database)

        self.cards: dict[str, StatCard] = {}

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        header_layout = QHBoxLayout()

        title_container = QVBoxLayout()
        title_container.setSpacing(2)

        title = QLabel("Dashboard")
        title.setObjectName("dashboardTitle")

        subtitle = QLabel(
            "Resumen financiero y operativo de Echando Chal"
        )
        subtitle.setObjectName("dashboardSubtitle")

        title_container.addWidget(title)
        title_container.addWidget(subtitle)

        refresh_button = QPushButton("Actualizar")
        refresh_button.setMinimumWidth(110)
        refresh_button.clicked.connect(self.refresh)

        header_layout.addLayout(title_container)
        header_layout.addStretch()
        header_layout.addWidget(refresh_button)

        main_layout.addLayout(header_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(22)

        # ---------------------------------------------------------
        # Ventas
        # ---------------------------------------------------------

        content_layout.addWidget(
            self._section_title("Ventas")
        )

        sales_grid = QGridLayout()
        sales_grid.setSpacing(12)

        self.cards["ventas_hoy"] = StatCard(
            "Ventas de hoy",
            subtitle="Importe bruto vendido",
        )

        self.cards["ventas_mes"] = StatCard(
            "Ventas del mes",
            subtitle="Importe bruto vendido",
        )

        self.cards["ventas_anio"] = StatCard(
            "Ventas del año",
            subtitle="Importe bruto vendido",
        )

        sales_grid.addWidget(
            self.cards["ventas_hoy"], 0, 0
        )
        sales_grid.addWidget(
            self.cards["ventas_mes"], 0, 1
        )
        sales_grid.addWidget(
            self.cards["ventas_anio"], 0, 2
        )

        content_layout.addLayout(sales_grid)

        # ---------------------------------------------------------
        # Ingreso neto y comisiones
        # ---------------------------------------------------------

        content_layout.addWidget(
            self._section_title(
                "Ingreso neto y comisiones"
            )
        )

        net_grid = QGridLayout()
        net_grid.setSpacing(12)

        self.cards["ingreso_neto_hoy"] = StatCard(
            "Ingreso neto de hoy",
            subtitle="Ventas menos comisiones",
        )

        self.cards["ingreso_neto_mes"] = StatCard(
            "Ingreso neto del mes",
            subtitle="Ventas menos comisiones",
        )

        self.cards["ingreso_neto_anio"] = StatCard(
            "Ingreso neto del año",
            subtitle="Ventas menos comisiones",
        )

        self.cards["comisiones_mes"] = StatCard(
            "Comisiones del mes",
            subtitle="Terminales y medios de pago",
        )

        net_grid.addWidget(
            self.cards["ingreso_neto_hoy"], 0, 0
        )
        net_grid.addWidget(
            self.cards["ingreso_neto_mes"], 0, 1
        )
        net_grid.addWidget(
            self.cards["ingreso_neto_anio"], 0, 2
        )
        net_grid.addWidget(
            self.cards["comisiones_mes"], 1, 0
        )

        content_layout.addLayout(net_grid)

        # ---------------------------------------------------------
        # Utilidad
        # ---------------------------------------------------------

        content_layout.addWidget(
            self._section_title("Utilidad")
        )

        profit_grid = QGridLayout()
        profit_grid.setSpacing(12)

        self.cards["utilidad_hoy"] = StatCard(
            "Utilidad de hoy",
            subtitle="Después de costo y comisiones",
        )

        self.cards["utilidad_mes"] = StatCard(
            "Utilidad del mes",
            subtitle="Después de costo y comisiones",
        )

        self.cards["utilidad_anio"] = StatCard(
            "Utilidad del año",
            subtitle="Después de costo y comisiones",
        )

        profit_grid.addWidget(
            self.cards["utilidad_hoy"], 0, 0
        )
        profit_grid.addWidget(
            self.cards["utilidad_mes"], 0, 1
        )
        profit_grid.addWidget(
            self.cards["utilidad_anio"], 0, 2
        )

        content_layout.addLayout(profit_grid)

        # ---------------------------------------------------------
        # Operación
        # ---------------------------------------------------------

        content_layout.addWidget(
            self._section_title("Operación")
        )

        operation_grid = QGridLayout()
        operation_grid.setSpacing(12)

        self.cards["ticket_promedio"] = StatCard(
            "Ticket promedio",
            subtitle="Promedio del mes",
        )

        self.cards["numero_ventas"] = StatCard(
            "Ventas realizadas",
            value="0",
            subtitle="Operaciones del mes",
        )

        self.cards["valor_inventario"] = StatCard(
            "Valor del inventario",
            subtitle="Valor actual a costo",
        )

        self.cards["stock_bajo"] = StatCard(
            "Stock bajo",
            value="0",
            subtitle="Productos por reabastecer",
        )

        operation_grid.addWidget(
            self.cards["ticket_promedio"], 0, 0
        )
        operation_grid.addWidget(
            self.cards["numero_ventas"], 0, 1
        )
        operation_grid.addWidget(
            self.cards["valor_inventario"], 0, 2
        )
        operation_grid.addWidget(
            self.cards["stock_bajo"], 0, 3
        )

        content_layout.addLayout(operation_grid)
        # ---------------------------------------------------------
        # Gráfica anual
        # ---------------------------------------------------------

        charts_container = QFrame()
        charts_container.setObjectName("chartsPlaceholder")

        charts_layout = QVBoxLayout(charts_container)
        charts_layout.setContentsMargins(16, 16, 16, 16)
        charts_layout.setSpacing(10)

        charts_title = QLabel(
            "Resumen financiero anual"
            )
        charts_title.setObjectName("chartTitle")
        self.annual_chart = AnnualFinancialChart()
        charts_layout.addWidget(charts_title)
        charts_layout.addWidget(self.annual_chart)

        content_layout.addWidget(charts_container)
        commission_container = QFrame()
        commission_container.setObjectName("chartsPlaceholder")

        commission_layout = QVBoxLayout(
            commission_container
        )
        commission_layout.setContentsMargins(
            16,
            16,
            16,
            16,
        )
        commission_layout.setSpacing(10)

        commission_title = QLabel(
            "Comisiones anuales"
        )
        commission_title.setObjectName("chartTitle")

        self.commission_chart = AnnualCommissionChart()

        commission_layout.addWidget(
            commission_title
        )
        commission_layout.addWidget(
            self.commission_chart
        )

        content_layout.addWidget(
            commission_container
        )
        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        self.setStyleSheet(
            """
            QLabel#dashboardTitle {
                font-size: 26px;
                font-weight: 700;
                }
            
            QLabel#dashboardSubtitle {
                font-size: 13px;
                color: #666666;
                }
            QLabel#sectionTitle {
                font-size: 17px;
                font-weight: 700;
                margin-top: 5px;
            }
            
            QFrame#statCard {
                border: 1px solid #d9d9d9;
                border-radius: 10px;
            }
            
            QLabel#cardTitle {
                font-size: 13px;
                font-weight: 600;
                color: #555555;
            }

            QLabel#cardValue {
                font-size: 25px;
                font-weight: 700;
                }

            QLabel#cardSubtitle {
                font-size: 11px;
                color: #777777;
                }

            QFrame#chartsPlaceholder {
                border: 1px solid #d9d9d9;
                border-radius: 10px;
                margin-top: 4px;
                }

            QLabel#chartTitle {
                font-size: 17px;
                font-weight: 700;
                }
                """
                )
    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    @staticmethod
    def _money(value: float) -> str:
        return f"${value:,.2f}"

    def refresh(self) -> None:
        """Actualiza todos los indicadores."""

        summary = self.service.get_summary()

        money_fields = (
            "ventas_hoy",
            "ventas_mes",
            "ventas_anio",
            "utilidad_hoy",
            "utilidad_mes",
            "utilidad_anio",
            "comisiones_mes",
            "ingreso_neto_hoy",
            "ingreso_neto_mes",
            "ingreso_neto_anio",
            "ticket_promedio",
            "valor_inventario",
        )

        for field in money_fields:
            self.cards[field].set_value(
                self._money(summary[field])
            )

        self.cards["numero_ventas"].set_value(
            f"{summary['numero_ventas']:,}"
        )

        self.cards["stock_bajo"].set_value(
            f"{summary['stock_bajo']:,}"
        )

        ventas_mes = summary["ventas_mes"]
        comisiones_mes = summary["comisiones_mes"]

        if ventas_mes > 0:
            porcentaje = (
                comisiones_mes / ventas_mes
            ) * 100
        else:
            porcentaje = 0.0

        self.cards["comisiones_mes"].set_subtitle(
            f"{porcentaje:.2f}% de las ventas del mes"
        )

        year = datetime.now().year

        annual_data = (
            self.service.get_monthly_financial_summary(
                year
            )
        )

        self.annual_chart.set_data(
            annual_data,
            year,
        )
        self.commission_chart.set_data(
            annual_data,
            year,
        )