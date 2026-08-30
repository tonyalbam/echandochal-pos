from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QValueAxis,
)
from PySide6.QtWidgets import QVBoxLayout, QWidget


class AnnualFinancialChart(QWidget):
    """Gráfica anual de ventas, ingreso neto y utilidad."""

    MONTHS = [
        "Ene",
        "Feb",
        "Mar",
        "Abr",
        "May",
        "Jun",
        "Jul",
        "Ago",
        "Sep",
        "Oct",
        "Nov",
        "Dic",
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setMinimumHeight(360)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.chart_view = QChartView()
        self.chart_view.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        self.layout.addWidget(self.chart_view)

    def set_data(
        self,
        data: list[dict],
        year: int,
    ) -> None:
        """Actualiza la gráfica con los datos de un año."""

        sales_set = QBarSet("Ventas")
        net_set = QBarSet("Ingreso neto")
        profit_set = QBarSet("Utilidad")

        for month in data:
            sales_set.append(
                float(month["ventas"])
            )
            net_set.append(
                float(month["ingreso_neto"])
            )
            profit_set.append(
                float(month["utilidad"])
            )

        series = QBarSeries()
        series.append(sales_set)
        series.append(net_set)
        series.append(profit_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(
            f"Ventas, ingreso neto y utilidad {year}"
        )
        chart.setAnimationOptions(
            QChart.AnimationOption.SeriesAnimations
        )

        axis_x = QBarCategoryAxis()
        axis_x.append(self.MONTHS)

        chart.addAxis(
            axis_x,
            Qt.AlignmentFlag.AlignBottom,
        )
        series.attachAxis(axis_x)

        max_value = 0.0

        for month in data:
            max_value = max(
                max_value,
                float(month["ventas"]),
                float(month["ingreso_neto"]),
                float(month["utilidad"]),
            )

        axis_y = QValueAxis()
        axis_y.setTitleText("Pesos")
        axis_y.setLabelFormat("$%.0f")
        axis_y.setRange(
            0,
            max(max_value * 1.15, 100),
        )

        chart.addAxis(
            axis_y,
            Qt.AlignmentFlag.AlignLeft,
        )
        series.attachAxis(axis_y)

        chart.legend().setVisible(True)
        chart.legend().setAlignment(
            Qt.AlignmentFlag.AlignBottom
        )

        self.chart_view.setChart(chart)