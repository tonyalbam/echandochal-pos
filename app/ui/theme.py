"""Tema global que sigue el modo de aplicaciones de Windows.

No guarda preferencias propias: Windows es la fuente de verdad. Al cambiar el
tema mientras el POS está abierto, el sondeo actualiza su paleta sin reiniciar.
"""

import sys

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def windows_uses_dark_mode() -> bool | None:
    """Lee la preferencia de aplicaciones (no la de la barra de tareas)."""
    if sys.platform != "win32":
        return None
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        with key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return int(value) == 0
    except (OSError, ValueError, TypeError):
        return None


def detect_dark_mode(app: QApplication) -> bool:
    setting = windows_uses_dark_mode()
    if setting is not None:
        return setting
    # En otros SO, o cuando el registro no es accesible, sigue la paleta.
    bg = app.style().standardPalette().color(QPalette.ColorRole.Window)
    return bg.lightness() < 128


def theme_colors(dark: bool) -> dict[str, str]:
    if dark:
        return {
            "window": "#171B22", "surface": "#242A34",
            "input": "#2B3240", "text": "#F4F6FA",
            "muted": "#BBC6D6", "border": "#485365",
            "accent": "#448ED4", "selection": "#285F91",
            "selection_text": "#FFFFFF", "disabled": "#8792A3",
            "card": "#253B59", "card_text": "#FFFFFF", "card_subtitle": "#DAE9FF",
            "row_alt": "#242F3D", "danger_row": "#743940",
            "success": "#80D7A4", "danger": "#FF9C9C",
        }
    return {
        "window": "#F5F7FB", "surface": "#FFFFFF",
        "input": "#FFFFFF", "text": "#202A36",
        "muted": "#536174", "border": "#CAD3E0",
        "accent": "#2869A3", "selection": "#2F75B5",
        "selection_text": "#FFFFFF", "disabled": "#7C8795",
        "card": "#24507C", "card_text": "#FFFFFF", "card_subtitle": "#DCEBFC",
        "row_alt": "#EDF3FA", "danger_row": "#F5A2A6",
        "success": "#176638", "danger": "#A52222",
    }


def build_palette(colors: dict[str, str]) -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: "window",
        QPalette.ColorRole.Mid: "border",
        QPalette.ColorRole.Dark: "border",
        QPalette.ColorRole.Light: "surface",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "input",
        QPalette.ColorRole.AlternateBase: "row_alt",
        QPalette.ColorRole.ToolTipBase: "surface",
        QPalette.ColorRole.ToolTipText: "text",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "surface",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.BrightText: "selection_text",
        QPalette.ColorRole.Highlight: "selection",
        QPalette.ColorRole.HighlightedText: "selection_text",
        QPalette.ColorRole.PlaceholderText: "muted",
        QPalette.ColorRole.Link: "accent",
    }
    for role, name in roles.items():
        palette.setColor(role, QColor(colors[name]))
    for role in (
        QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled, role, QColor(colors["disabled"])
        )
    return palette


def build_stylesheet(colors: dict[str, str]) -> str:
    c = colors
    return f"""
        QWidget {{
            background-color: {c['window']};
            color: {c['text']};
        }}
        QMainWindow, QDialog, QScrollArea, QScrollArea > QWidget > QWidget {{
            background-color: {c['window']};
            color: {c['text']};
        }}
        QFrame {{
            color: {c['text']};
        }}
        QLabel, QCheckBox, QRadioButton, QGroupBox {{
            color: {c['text']};
            background: transparent;
        }}
        QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox,
        QDateEdit, QTimeEdit, QDateTimeEdit, QComboBox {{
            background-color: {c['input']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            padding: 4px;
            selection-background-color: {c['selection']};
            selection-color: {c['selection_text']};
        }}
        QComboBox QAbstractItemView, QListView, QListWidget {{
            background-color: {c['surface']};
            color: {c['text']};
            border: 1px solid {c['border']};
            selection-background-color: {c['selection']};
            selection-color: {c['selection_text']};
        }}
        QTableView, QTableWidget, QTreeView, QTreeWidget {{
            background-color: {c['surface']};
            alternate-background-color: {c['row_alt']};
            color: {c['text']};
            gridline-color: {c['border']};
            border: 1px solid {c['border']};
            selection-background-color: {c['selection']};
            selection-color: {c['selection_text']};
        }}
        QTableView::item:selected, QTableWidget::item:selected,
        QListView::item:selected, QTreeView::item:selected {{
            background-color: {c['selection']};
            color: {c['selection_text']};
        }}
        QHeaderView::section {{
            background-color: {c['surface']};
            color: {c['text']};
            border: 1px solid {c['border']};
            padding: 5px;
        }}
        QPushButton {{
            color: {c['text']};
            background-color: {c['surface']};
            border: 1px solid {c['border']};
            border-radius: 5px;
            padding: 6px 10px;
        }}
        QPushButton:hover {{
            border-color: {c['accent']};
            background-color: {c['row_alt']};
        }}
        QPushButton:pressed {{
            background-color: {c['selection']};
            color: {c['selection_text']};
        }}
        QPushButton:disabled {{
            color: {c['disabled']};
            border-color: {c['border']};
        }}
        QTabWidget::pane {{
            border: 1px solid {c['border']};
            background-color: {c['window']};
        }}
        QTabBar::tab {{
            background-color: {c['surface']};
            color: {c['text']};
            border: 1px solid {c['border']};
            padding: 8px 13px;
        }}
        QTabBar::tab:selected {{
            background-color: {c['selection']};
            color: {c['selection_text']};
        }}
        QScrollBar {{
            background: {c['window']};
        }}
        QScrollBar::handle {{
            background: {c['border']};
            border-radius: 4px;
        }}
        QToolTip {{
            background-color: {c['surface']};
            color: {c['text']};
            border: 1px solid {c['border']};
        }}
        QMessageBox QLabel {{
            background: transparent;
            color: {c['text']};
        }}
    """


class WindowsThemeManager(QObject):
    """Mantiene el tema de QApplication sincronizado con Windows."""

    theme_changed = Signal(bool)

    def __init__(self, app: QApplication, parent=None):
        super().__init__(parent or app)
        self.app = app
        self.dark_mode: bool | None = None
        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.refresh)
        self.refresh()
        self.timer.start()

    def refresh(self) -> None:
        dark = detect_dark_mode(self.app)
        if dark == self.dark_mode:
            return
        self.dark_mode = dark
        self.app.setProperty("echandochal_dark_mode", dark)
        colors = theme_colors(dark)
        self.app.setPalette(build_palette(colors))
        self.app.setStyleSheet(build_stylesheet(colors))
        self.theme_changed.emit(dark)
