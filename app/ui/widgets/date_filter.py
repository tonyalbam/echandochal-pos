"""Selector de fechas editable con botón de calendario siempre visible.

El QDateEdit nativo puede quedar sin flecha visible por el tema de Qt.
Este botón abre un calendario real sin depender del estilo del spin box.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCalendarWidget, QDateEdit, QDialog, QHBoxLayout, QToolButton, QWidget,
)


def add_calendar_button(layout: QHBoxLayout, field: QDateEdit, parent: QWidget):
    """Agrega un calendario desplegable accesible a un QDateEdit editable."""
    field.setReadOnly(False)
    field.setCalendarPopup(True)
    field.setKeyboardTracking(False)
    field.setMinimumWidth(125)
    field.setToolTip(
        "Puedes escribir la fecha o elegirla desde el botón de calendario."
    )
    button = QToolButton(parent)
    button.setText("📅")
    button.setToolTip("Seleccionar fecha en el calendario")
    button.setAccessibleName("Abrir calendario de fecha")
    button.setFixedWidth(36)

    popup = QDialog(parent, Qt.WindowType.Popup)
    popup.setObjectName("datePickerPopup")
    popup_layout = QHBoxLayout(popup)
    popup_layout.setContentsMargins(4, 4, 4, 4)
    calendar = QCalendarWidget(popup)
    calendar.setObjectName("datePickerCalendar")
    calendar.setGridVisible(True)
    popup_layout.addWidget(calendar)

    def apply_date(selected):
        field.setDate(selected)
        popup.hide()
        field.setFocus()

    def open_calendar():
        calendar.setMinimumDate(field.minimumDate())
        calendar.setMaximumDate(field.maximumDate())
        calendar.setSelectedDate(field.date())
        popup.adjustSize()
        popup.move(button.mapToGlobal(button.rect().bottomLeft()))
        popup.show()
        calendar.setFocus()

    calendar.clicked.connect(apply_date)
    button.clicked.connect(open_calendar)
    layout.addWidget(button)
    # Mantener referencias para el uso desde pruebas y evitar GC.
    button.calendar_popup = popup
    button.calendar_widget = calendar
    return button
