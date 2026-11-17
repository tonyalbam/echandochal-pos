"""Vista previa e impresión de tickets PDF dentro de Echando Chal POS.

Los archivos utilizados por este diálogo son temporales y el propietario
debe mantenerlos durante toda la vida de la ventana.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, QSize, QSizeF
from PySide6.QtGui import QPageSize, QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class TicketPreviewDialog(QDialog):
    """Muestra el PDF del mismo ticket que puede guardarse o imprimirse."""

    def __init__(self, pdf_path: str | Path, folio: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Ticket de venta · {folio}")
        self.resize(650, 740)
        self.setMinimumSize(410, 430)

        # Abrir el PDF desde memoria evita que PDFium bloquee el archivo
        # temporal en Windows después de cerrar la vista previa.
        self._pdf_data = QByteArray(Path(pdf_path).read_bytes())
        self._pdf_buffer = QBuffer(self)
        self._pdf_buffer.setData(self._pdf_data)
        if not self._pdf_buffer.open(QIODevice.OpenModeFlag.ReadOnly):
            raise OSError("No se pudo preparar el ticket para su visualización.")

        self.document = QPdfDocument(self)
        self.document.load(self._pdf_buffer)
        if self.document.pageCount() < 1:
            error = self.document.error()
            self.document.close()
            self._pdf_buffer.close()
            raise ValueError(f"No se pudo abrir el PDF del ticket: {error}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel(f"Vista previa del ticket · {folio}")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        self.pdf_view = QPdfView(self)
        self.pdf_view.setDocument(self.document)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        layout.addWidget(self.pdf_view, 1)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Imprimir utiliza las impresoras de Windows."))
        controls.addStretch()

        self.print_button = QPushButton("Imprimir")
        self.print_button.setMinimumSize(125, 40)
        self.print_button.clicked.connect(self._print_ticket)
        controls.addWidget(self.print_button)

        close_button = QPushButton("Cerrar")
        close_button.setMinimumSize(100, 40)
        close_button.clicked.connect(self.accept)
        controls.addWidget(close_button)
        layout.addLayout(controls)

    def release_document(self) -> None:
        """Libera el archivo para permitir borrar el PDF temporal en Windows."""
        self.pdf_view.setDocument(None)
        self.document.close()
        self._pdf_buffer.close()

    def _print_ticket(self) -> None:
        """El operador elige impresora; el PDF se imprime sin guardarlo."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        size = self.document.pagePointSize(0)
        if size.isValid():
            # Por defecto se propone el tamaño original del ticket.
            printer.setPageSize(QPageSize(QSizeF(size), QPageSize.Unit.Point))

        print_dialog = QPrintDialog(printer, self)
        print_dialog.setWindowTitle("Imprimir ticket")
        if print_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            print_pdf_document(self.document, printer)
        except (OSError, RuntimeError, ValueError) as error:
            QMessageBox.warning(self, "No se pudo imprimir", str(error))


def print_pdf_document(document: QPdfDocument, printer: QPrinter) -> None:
    """Imprime cada página PDF en el dispositivo elegido, a escala natural.

    Si el área imprimible no cabe, reduce proporcionalmente para evitar
    cortes; nunca amplía el ticket en papel tamaño carta/A4.
    """
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("No fue posible iniciar el trabajo de impresión.")

    try:
        for page in range(document.pageCount()):
            if page and not printer.newPage():
                raise RuntimeError("No se pudo continuar la impresión.")
            point_size = document.pagePointSize(page)
            if not point_size.isValid():
                raise RuntimeError("El ticket contiene una página inválida.")

            render_dpi = 200
            render_size = QSize(
                max(1, round(point_size.width() * render_dpi / 72)),
                max(1, round(point_size.height() * render_dpi / 72)),
            )
            image = document.render(page, render_size)
            if image.isNull():
                raise RuntimeError("No se pudo renderizar el ticket.")

            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            physical_width = point_size.width() * printer.logicalDpiX() / 72
            physical_height = point_size.height() * printer.logicalDpiY() / 72
            scale = min(
                1.0,
                page_rect.width() / physical_width,
                page_rect.height() / physical_height,
            )
            if scale <= 0:
                raise RuntimeError("La impresora no tiene un área imprimible válida.")
            width = physical_width * scale
            height = physical_height * scale
            x = page_rect.x() + (page_rect.width() - width) / 2
            y = page_rect.y()
            painter.drawImage(QRectF(x, y, width, height), image)
    except Exception:
        painter.end()
        raise

    if not painter.end():
        raise RuntimeError("La impresora no pudo finalizar el documento.")

def print_sale_ticket_to_printer(ticket_service, sale_id: int, printer: QPrinter) -> None:
    """Genera y manda un ticket a la impresora sin solicitar guardarlo.

    PDFium recibe un búfer en memoria. Así no retiene bloqueos de archivos
    temporales en Windows, incluso si la impresión falla.
    """
    with TemporaryDirectory(prefix="echandochal-print-") as directory:
        path = ticket_service.generate_sale_ticket(
            sale_id, Path(directory) / "recibo.pdf"
        )
        pdf_data = QByteArray(Path(path).read_bytes())
        buffer = QBuffer()
        buffer.setData(pdf_data)
        if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
            raise OSError("No se pudo preparar el PDF para imprimir.")

        document = QPdfDocument()
        try:
            document.load(buffer)
            if document.pageCount() < 1:
                raise ValueError("No se pudo abrir el ticket para imprimir.")

            size = document.pagePointSize(0)
            if size.isValid():
                printer.setPageSize(
                    QPageSize(QSizeF(size), QPageSize.Unit.Point)
                )
            print_pdf_document(document, printer)
        finally:
            document.close()
            buffer.close()

