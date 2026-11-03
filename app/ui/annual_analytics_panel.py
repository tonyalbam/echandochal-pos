"""Panel de analítica anual de Echando Chal POS."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView,
)
from app.ui.widgets.annual_analytics_charts import (
    CumulativeProfitChart, RevenueDonutChart,
)
from app.ui.theme import theme_colors
from app.ui.widgets.column_sort import SortableItem, install_table_sort, restore_table_sort

def _money(value: float) -> str:
    return f"$ {value:,.2f}"


class AnnualAnalyticsCard(QFrame):
    def __init__(self, heading: str, icon: str, parent=None):
        super().__init__(parent)
        self.setObjectName("analyticsCard")
        self.setMinimumHeight(150)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        self.icon_label = QLabel(icon)
        self.icon_label.setObjectName("analyticsIcon")
        self.title_label = QLabel(heading)
        self.title_label.setObjectName("analyticsCardHeading")
        self.value = QLabel("Sin datos")
        self.value.setObjectName("analyticsValue")
        self.value.setWordWrap(True)
        self.value.setMinimumHeight(36)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("analyticsSubtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.value)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle)
        layout.addStretch()

    def update_contents(self, value: str, detail: str) -> None:
        self.value.setText(value)
        self.subtitle.setText(detail)


class AnnualAnalyticsPanel(QWidget):
    MONTH_NAMES = (
        "Ene", "Feb", "Mar", "Abr", "May", "Jun",
        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
    )
    CHART_COLORS = ("#319BD8", "#27BF78", "#F6A51B", "#E44E52", "#A16AC3")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dark = False
        self._latest = None
        self._build_ui()
        self.apply_theme(False)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 12, 8, 12)
        outer.setSpacing(18)

        title = QLabel("Panorama anual del negocio")
        title.setObjectName("analyticsTitle")
        outer.addWidget(title)
        self.period = QLabel("Datos del año en curso")
        self.period.setObjectName("analyticsSecondary")
        outer.addWidget(self.period)

        indicators = QGridLayout()
        indicators.setSpacing(12)
        self.brand = AnnualAnalyticsCard("Marca más vendida", "◆")
        self.units = AnnualAnalyticsCard("Producto líder por unidades", "★")
        self.profit = AnnualAnalyticsCard("Producto más rentable", "◈")
        self.slowest = AnnualAnalyticsCard("Menor rotación (90+ días)", "◷")
        for index, card in enumerate(
            (self.brand, self.units, self.profit, self.slowest)
        ):
            indicators.addWidget(card, 0, index)
        outer.addLayout(indicators)

        charts = QHBoxLayout()
        charts.setSpacing(14)
        self.performance_frame = QFrame()
        self.performance_frame.setObjectName("analyticsPanel")
        performance_layout = QVBoxLayout(self.performance_frame)
        performance_layout.addWidget(self._heading(
            "Utilidad acumulada por mes"
        ))
        self.performance_chart = CumulativeProfitChart()
        self.performance_chart.setMinimumHeight(340)
        performance_layout.addWidget(self.performance_chart)
        charts.addWidget(self.performance_frame, 3)

        self.pie_frame = QFrame()
        self.pie_frame.setObjectName("analyticsPanel")
        pie_layout = QVBoxLayout(self.pie_frame)
        pie_layout.addWidget(self._heading(
            "Top 5 productos por monto de ventas"
        ))
        self.pie_chart = RevenueDonutChart()
        self.pie_chart.setMinimumHeight(340)
        pie_layout.addWidget(self.pie_chart)
        charts.addWidget(self.pie_frame, 2)
        outer.addLayout(charts)

        inventory_frame = QFrame()
        inventory_frame.setObjectName("analyticsPanel")
        inventory_layout = QVBoxLayout(inventory_frame)
        inventory_layout.addWidget(self._heading(
            "Inventario sin ventas durante más de 90 días"
        ))
        note = QLabel(
            "Productos activos con existencias. Los que nunca se han vendido "
            "se cuentan desde su fecha de alta."
        )
        note.setObjectName("analyticsSecondary")
        note.setWordWrap(True)
        inventory_layout.addWidget(note)

        self.stagnant = QTableWidget(0, 10)
        self.stagnant.setHorizontalHeaderLabels([
            "Código", "Producto", "Marca", "Categoría", "Existencia",
            "Última venta", "Días sin vender", "Costo",
            "Precio venta", "Valor inmovilizado",
        ])
        self.stagnant.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.stagnant.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.stagnant.setAlternatingRowColors(True)
        self.stagnant.setMinimumHeight(260)
        self.stagnant.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.stagnant.horizontalHeader().setStretchLastSection(True)
        install_table_sort(self.stagnant)
        inventory_layout.addWidget(self.stagnant)
        outer.addWidget(inventory_frame)

    @staticmethod
    def _heading(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("analyticsHeading")
        return label

    def set_data(self, summary: dict) -> None:
        self._latest = summary
        year = summary["year"]
        self.period.setText(f"Indicadores acumulados del año {year}")

        brand = summary["marca_mas_vendida"]
        self.brand.update_contents(
            brand["nombre"] if brand else "Sin ventas",
            f"{brand['unidades']:g} unidades vendidas" if brand else "Sin datos en el año",
        )
        product = summary["producto_mas_vendido"]
        self.units.update_contents(
            product["nombre"] if product else "Sin ventas",
            (
                f"{product['unidades']:g} unidades · {product['categoria']}"
                if product else "Sin datos en el año"
            ),
        )
        most_profitable = summary["producto_mas_rentable"]
        self.profit.update_contents(
            most_profitable["nombre"] if most_profitable else "Sin ventas",
            (
                f"Utilidad anual: {_money(most_profitable['utilidad'])}"
                if most_profitable else "Sin datos en el año"
            ),
        )
        slowest = summary["producto_menos_vendido"]
        self.slowest.update_contents(
            slowest["nombre"] if slowest else "Sin productos elegibles",
            (
                f"{slowest['unidades']:g} unidades vendidas · "
                f"{slowest['dias']} días en inventario"
                if slowest else "Ningún producto con 90 días en inventario"
            ),
        )

        self.stagnant.setRowCount(0)
        for index, product in enumerate(summary["sin_venta_90_dias"]):
            self.stagnant.insertRow(index)
            values = (
                product["codigo"], product["nombre"], product["marca"],
                product["categoria"], f"{product['existencia']:g}",
                product["ultima_venta"] or "Nunca",
                str(product["dias_sin_venta"]), _money(product["costo"]),
                _money(product["precio"]),
                _money(product["valor_inmovilizado"]),
            )
            for col, value in enumerate(values):
                cell = SortableItem(value, numeric=col in [4,6,7,8,9])
                if col in (4, 6, 7, 8, 9):
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight |
                        Qt.AlignmentFlag.AlignVCenter
                    )
                self.stagnant.setItem(index, col, cell)

        self._render_performance(summary["utilidad_acumulada"])
        restore_table_sort(self.stagnant)
        self._render_revenue_pie(summary["top_productos_ingresos"])

    def _render_performance(self, months: list[dict]) -> None:
        self.performance_chart.set_data(months)

    def _render_revenue_pie(self, products: list[dict]) -> None:
        self.pie_chart.set_data(products)

    def apply_theme(self, dark: bool) -> None:
        self._dark = bool(dark)
        colors = theme_colors(dark)
        self.setStyleSheet(f"""
            QFrame#analyticsCard, QFrame#analyticsPanel {{
                background: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 13px;
            }}
            QFrame#analyticsCard {{
                background: {colors['card']};
                border-radius: 15px;
            }}
            QLabel#analyticsValue {{
                font-size: 20px; font-weight: bold;
                color: {colors['card_text']};
                background: transparent; border: none;
            }}
            QLabel#analyticsCardHeading {{
                font-size: 13px; font-weight: 600;
                color: {colors['card_subtitle']};
                background: transparent; border: none;
            }}
            QLabel#analyticsSubtitle {{
                font-size: 12px; color: {colors['card_subtitle']};
                background: transparent; border: none;
            }}
            QLabel#analyticsIcon {{
                font-size: 26px; color: #319BD8;
                background: transparent; border: none;
            }}
            QLabel#analyticsTitle {{
                font-size: 22px; font-weight: bold;
                color: {colors['text']};
            }}
            QLabel#analyticsHeading {{
                font-size: 17px; font-weight: bold;
                color: {colors['text']};
                border: none; background: transparent;
            }}
            QLabel#analyticsSecondary {{
                color: {colors['muted']};
                background: transparent; border: none;
            }}
        """)
        self.performance_chart.apply_theme(dark)
        self.pie_chart.apply_theme(dark)
