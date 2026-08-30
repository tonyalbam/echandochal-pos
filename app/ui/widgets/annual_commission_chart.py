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


class AnnualCommissionChart(QWidget):
    """Gráfica anual de comisiones."""

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

        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.chart_view = QChartView()
        self.chart_view.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        layout.addWidget(self.chart_view)

    def set_data(
        self,
        data: list[dict],
        year: int,
    ) -> None:
        """Actualiza la gráfica con las comisiones del año."""

        commission_set = QBarSet("Comisiones")

        max_value = 0.0

        for month in data:
            value = float(month["comisiones"])
            commission_set.append(value)
            max_value = max(max_value, value)

        series = QBarSeries()
        series.append(commission_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(
            f"Comisiones mensuales {year}"
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

        axis_y = QValueAxis()
        axis_y.setTitleText("Pesos")
        axis_y.setLabelFormat("$%.0f")
        axis_y.setRange(
            0,
            max(max_value * 1.20, 10),
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