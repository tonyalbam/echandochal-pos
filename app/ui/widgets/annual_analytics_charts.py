"""Gráficas ligeras para Analítica anual, sin QChart ni objetos nativos compartidos."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from app.ui.theme import theme_colors

MONTHS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun",
          "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
SEGMENT_COLORS = ("#319BD8", "#27BF78", "#F6A51B", "#E44E52", "#A16AC3")


def money(value: float) -> str:
    return f"$ {value:,.2f}"


class CumulativeProfitChart(QWidget):
    """Línea y área sombreada, con escala que admite utilidades negativas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.months = []
        self.dark = False
        self.setMinimumHeight(340)

    def set_data(self, months):
        self.months = list(months)
        self.update()

    def apply_theme(self, dark):
        self.dark = bool(dark)
        self.update()

    def paintEvent(self, event):
        colors = theme_colors(self.dark)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        p.fillRect(bounds, QColor(colors["surface"]))
        if bounds.width() < 120 or bounds.height() < 100:
            p.end()
            return
        graph = QRectF(bounds.left() + 66, bounds.top() + 14,
                       bounds.width() - 83, bounds.height() - 61)
        values = [float(item["acumulada"]) for item in self.months]
        if not values:
            p.setPen(QColor(colors["muted"]))
            p.drawText(bounds, Qt.AlignmentFlag.AlignCenter, "Sin datos del año")
            p.end()
            return

        low = min(0.0, *values)
        high = max(0.0, *values)
        margin = max(20.0, (high - low) * .12)
        low -= margin
        high += margin
        span = max(1.0, high - low)

        def y_of(value):
            return graph.bottom() - (value - low) / span * graph.height()

        def x_of(index):
            return graph.left() + index / max(1, len(values) - 1) * graph.width()

        p.setFont(QFont(self.font().family(), 9))
        for tick in range(5):
            value = low + tick * span / 4
            y = y_of(value)
            p.setPen(QPen(QColor(colors["border"]), 1))
            p.drawLine(QPointF(graph.left(), y), QPointF(graph.right(), y))
            p.setPen(QColor(colors["muted"]))
            p.drawText(
                QRectF(bounds.left(), y - 10, 59, 20),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{value:,.0f}",
            )
        for index, month in enumerate(MONTHS[:len(values)]):
            p.setPen(QColor(colors["muted"]))
            p.drawText(
                QRectF(x_of(index) - 18, graph.bottom() + 10, 36, 20),
                Qt.AlignmentFlag.AlignCenter, month,
            )
        baseline = y_of(0)
        area = QPainterPath(QPointF(x_of(0), baseline))
        line = QPainterPath()
        for index, value in enumerate(values):
            point = QPointF(x_of(index), y_of(value))
            if index == 0:
                line.moveTo(point)
            else:
                line.lineTo(point)
            area.lineTo(point)
        area.lineTo(QPointF(x_of(len(values) - 1), baseline))
        area.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(49, 155, 216, 58)))
        p.drawPath(area)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#319BD8"), 3))
        p.drawPath(line)
        p.setBrush(QColor("#319BD8"))
        for index, value in enumerate(values):
            p.drawEllipse(QPointF(x_of(index), y_of(value)), 3, 3)
        p.end()


class RevenueDonutChart(QWidget):
    """Dona y leyenda de los cinco productos con mayores ventas en pesos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.products = []
        self.dark = False
        self.setMinimumHeight(340)

    def set_data(self, products):
        self.products = [dict(row) for row in products if row["ventas"] > 0][:5]
        self.update()

    def apply_theme(self, dark):
        self.dark = bool(dark)
        self.update()

    def paintEvent(self, event):
        colors = theme_colors(self.dark)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        p.fillRect(bounds, QColor(colors["surface"]))
        total = sum(float(row["ventas"]) for row in self.products)
        if total <= 0:
            p.setPen(QColor(colors["muted"]))
            p.drawText(bounds, Qt.AlignmentFlag.AlignCenter, "Sin ventas registradas")
            p.end()
            return
        available = min(bounds.height() - 32, bounds.width() * .48)
        diameter = max(48.0, available - 30)
        center_x = bounds.left() + bounds.width() * .30
        center_y = bounds.center().y()
        circle = QRectF(center_x - diameter / 2, center_y - diameter / 2,
                        diameter, diameter)
        thickness = max(12, diameter * .21)
        rect = circle.adjusted(thickness / 2, thickness / 2,
                               -thickness / 2, -thickness / 2)
        start = 90 * 16
        for index, row in enumerate(self.products):
            portion = float(row["ventas"]) / total
            angle = int(round(portion * 360 * 16))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(SEGMENT_COLORS[index]), thickness,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            p.drawArc(rect, start, -angle)
            start -= angle
        p.setPen(QColor(colors["text"]))
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSize(13)
        p.setFont(font)
        p.drawText(circle, Qt.AlignmentFlag.AlignCenter, "100%")
        legend_left = bounds.left() + bounds.width() * .60
        legend_width = max(40, bounds.right() - legend_left)
        p.setFont(QFont(self.font().family(), 9))
        row_h = min(59, (bounds.height() - 16) / max(1, len(self.products)))
        for index, row in enumerate(self.products):
            top = bounds.top() + 10 + index * row_h
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(SEGMENT_COLORS[index]))
            p.drawEllipse(QRectF(legend_left, top + 5, 11, 11))
            p.setPen(QColor(colors["text"]))
            name = str(row["nombre"])
            metrics = p.fontMetrics()
            name = metrics.elidedText(name, Qt.TextElideMode.ElideRight,
                                      max(10, int(legend_width - 21)))
            p.drawText(
                QRectF(legend_left + 17, top, legend_width - 17, 20),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                name,
            )
            p.setPen(QColor(colors["muted"]))
            p.drawText(
                QRectF(legend_left + 17, top + 19, legend_width - 17, 24),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{100 * float(row['ventas']) / total:.1f}%  {money(row['ventas'])}",
            )
        p.end()
