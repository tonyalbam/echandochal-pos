"""Confirmación rápida de impresión tras registrar una venta."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class SaleReceiptPrompt(QDialog):
    """Enter/I imprime; C/Escape/cerrar continúa sin imprimir."""

    def __init__(self, sale: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Venta registrada")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        title = QLabel("Venta registrada correctamente")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        summary = QLabel(
            f"Folio: {sale['folio']}\n"
            f"Total: $ {sale['total']:,.2f}\n"
            f"Cambio: $ {sale['change']:,.2f}"
        )
        layout.addWidget(summary)

        question = QLabel("¿Imprimir el recibo?")
        question.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(question)

        hint = QLabel(
            "Enter o I: imprimir en la impresora predeterminada. "
            "C o Esc: no imprimir."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        actions = QHBoxLayout()
        self.skip_button = QPushButton("No imprimir (C / Esc)")
        self.skip_button.setMinimumHeight(42)
        self.skip_button.setAutoDefault(False)
        self.skip_button.clicked.connect(self.reject)

        self.print_button = QPushButton("Imprimir (Enter / I)")
        self.print_button.setMinimumHeight(42)
        self.print_button.setDefault(True)
        self.print_button.clicked.connect(self.accept)

        actions.addWidget(self.skip_button)
        actions.addWidget(self.print_button)
        layout.addLayout(actions)

    def keyPressEvent(self, event) -> None:
        if not event.modifiers() and event.key() in (
            Qt.Key.Key_C,
            Qt.Key.Key_Escape,
        ):
            self.reject()
            event.accept()
            return
        if not event.modifiers() and event.key() in (
            Qt.Key.Key_I,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            self.accept()
            event.accept()
            return
        super().keyPressEvent(event)
