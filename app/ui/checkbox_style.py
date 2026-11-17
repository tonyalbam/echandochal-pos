"""Indicadores de casilla accesibles y visibles para todos los temas de Qt.

Se usa un QProxyStyle a nivel de aplicacion para que las casillas de todas
las ventanas (incluidos dialogos) compartan el mismo aspecto sin depender
de los iconos del tema del sistema operativo.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QProxyStyle, QStyle


class AccessibleCheckboxStyle(QProxyStyle):
    """Dibuja casillas de 20 px, con borde y marca de alto contraste."""

    INDICATOR_SIZE = 20

    def pixelMetric(self, metric, option=None, widget=None):
        if metric in (
            QStyle.PixelMetric.PM_IndicatorWidth,
            QStyle.PixelMetric.PM_IndicatorHeight,
        ):
            return self.INDICATOR_SIZE
        return super().pixelMetric(metric, option, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element != QStyle.PrimitiveElement.PE_IndicatorCheckBox:
            return super().drawPrimitive(element, option, painter, widget)

        state = option.state
        enabled = bool(state & QStyle.StateFlag.State_Enabled)
        checked = bool(state & QStyle.StateFlag.State_On)
        partial = bool(state & QStyle.StateFlag.State_NoChange)
        hovered = bool(state & QStyle.StateFlag.State_MouseOver)
        dark = option.palette.color(QPalette.ColorRole.Window).lightness() < 128

        if not enabled:
            fill = "#64748B" if (checked or partial) else (
                "#475569" if dark else "#E5E7EB"
            )
            outline = "#94A3B8" if dark else "#9CA3AF"
            mark = "#F8FAFC"
        elif checked or partial:
            fill = "#1769C2"
            outline = "#60A5FA" if hovered else "#0E4F96"
            mark = "#FFFFFF"
        else:
            fill = "#293544" if dark else "#FFFFFF"
            outline = "#93C5FD" if hovered else (
                "#CBD5E1" if dark else "#475569"
            )
            mark = "#FFFFFF"

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(option.rect).adjusted(1.5, 1.5, -1.5, -1.5)
        painter.setPen(QPen(QBrush(QColor(outline)), 2))
        painter.setBrush(QBrush(QColor(fill)))
        painter.drawRoundedRect(rect, 3.5, 3.5)

        if checked or partial:
            x, y, w, h = (rect.x(), rect.y(), rect.width(), rect.height())
            check = QPainterPath()
            if partial:
                check.moveTo(x + w * 0.23, y + h * 0.5)
                check.lineTo(x + w * 0.77, y + h * 0.5)
            else:
                check.moveTo(x + w * 0.22, y + h * 0.52)
                check.lineTo(x + w * 0.42, y + h * 0.71)
                check.lineTo(x + w * 0.79, y + h * 0.29)
            painter.setPen(
                QPen(
                    QBrush(QColor(mark)),
                    2.6,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(check)

        painter.restore()
