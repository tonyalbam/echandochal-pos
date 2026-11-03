"""Panel de analítica anual de Echando Chal POS."""

from PySide6.QtCore import Qt
from PySide6.QtCharts import (
    QAreaSeries, QChart, QChartView, QLineSeries, QPieSeries,
    QValueAxis, QCategoryAxis,
)
from PySide6.QtGui import QColor, QBrush, QPen, QPainter
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView,
)

from app.ui.theme import theme_colors


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
        self.slowest = AnnualAnalyticsCard("Menor rotación", "◷")
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
        self.performance_chart = QChartView()
        self.performance_chart.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )
        self.performance_chart.setMinimumHeight(340)
        performance_layout.addWidget(self.performance_chart)
        charts.addWidget(self.performance_frame, 3)

        self.pie_frame = QFrame()
        self.pie_frame.setObjectName("analyticsPanel")
        pie_layout = QVBoxLayout(self.pie_frame)
        pie_layout.addWidget(self._heading(
            "Top 5 productos por monto de ventas"
        ))
        self.pie_chart = QChartView()
        self.pie_chart.setRenderHint(QPainter.RenderHint.Antialiasing)
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
            slowest["nombre"] if slowest else "Sin productos",
            (
                f"{slowest['unidades']:g} unidades vendidas · "
                f"{slowest['dias']} días en inventario"
                if slowest else "Sin existencias activas"
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
                cell = QTableWidgetItem(value)
                if col in (4, 6, 7, 8, 9):
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight |
                        Qt.AlignmentFlag.AlignVCenter
                    )
                self.stagnant.setItem(index, col, cell)

        self._render_performance(summary["utilidad_acumulada"])
        self._render_revenue_pie(summary["top_productos_ingresos"])

    def _chart_base(self) -> QChart:
        colors = theme_colors(self._dark)
        chart = QChart()
        chart.setBackgroundBrush(QBrush(QColor(colors["surface"])))
        chart.setPlotAreaBackgroundBrush(QBrush(QColor(colors["surface"])))
        chart.setPlotAreaBackgroundVisible(True)
        chart.setTitleBrush(QBrush(QColor(colors["text"])))
        return chart

    def _render_performance(self, months: list[dict]) -> None:
        colors = theme_colors(self._dark)
        chart = self._chart_base()
        chart.legend().hide()

        line = QLineSeries()
        line.setPen(QPen(QColor("#319BD8"), 3))
        upper = QLineSeries()
        for row in months:
            line.append(row["mes"], float(row["acumulada"]))
            upper.append(row["mes"], float(row["acumulada"]))

        floor = min(0.0, *(float(row["acumulada"]) for row in months))
        ceiling = max(0.0, *(float(row["acumulada"]) for row in months))
        margin = max((ceiling - floor) * .12, 20.0)
        baseline = QLineSeries()
        for row in months:
            baseline.append(row["mes"], min(0.0, floor))
        area = QAreaSeries(upper, baseline)
        area.setBrush(QBrush(QColor(49, 155, 216, 58)))
        area.setPen(QPen(Qt.PenStyle.NoPen))
        chart.addSeries(area)
        chart.addSeries(line)

        axis_x = QCategoryAxis()
        axis_x.setRange(1, 12)
        axis_x.setLabelsPosition(
            QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionOnValue
        )
        for number, name in enumerate(self.MONTH_NAMES, 1):
            axis_x.append(name, number)
        axis_y = QValueAxis()
        axis_y.setRange(floor - margin, ceiling + margin)
        axis_y.setLabelFormat("$%.0f")
        axis_y.setTitleText("Utilidad acumulada (MXN)")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        for series in (area, line):
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)
        for axis in (axis_x, axis_y):
            axis.setLabelsBrush(QBrush(QColor(colors["text"])))
            axis.setTitleBrush(QBrush(QColor(colors["text"])))
            axis.setGridLineColor(QColor(colors["border"]))
        self.performance_chart.setChart(chart)

    def _render_revenue_pie(self, products: list[dict]) -> None:
        colors = theme_colors(self._dark)
        chart = self._chart_base()
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
        chart.legend().setLabelBrush(QBrush(QColor(colors["text"])))
        chart.legend().setFont(self.font())

        pie = QPieSeries()
        pie.setHoleSize(.52)
        pie.setPieSize(.78)
        for index, row in enumerate(products):
            if row["ventas"] <= 0:
                continue
            label = (
                f"{row['nombre']}\n"
                f"{row['porcentaje']:.1f}% · {_money(row['ventas'])}"
            )
            slice_ = pie.append(label, float(row["ventas"]))
            slice_.setBrush(QBrush(QColor(
                self.CHART_COLORS[index % len(self.CHART_COLORS)]
            )))
            slice_.setBorderColor(QColor(colors["surface"]))
            slice_.setBorderWidth(2)
        chart.addSeries(pie)
        if not products:
            chart.setTitle("Sin ventas registradas")
        self.pie_chart.setChart(chart)

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
        if self._latest is not None:
            self._render_performance(self._latest["utilidad_acumulada"])
            self._render_revenue_pie(self._latest["top_productos_ingresos"])
