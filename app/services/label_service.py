from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import code128
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.database.connection import Database
from app.services.product_service import ProductService


class LabelService:
    """Genera etiquetas escaneables para productos."""

    FORMATS = ("Código de barras", "Código QR", "Ambos")

    def __init__(self, database: Database) -> None:
        self.products = ProductService(database)

    def generate_product_label(
        self,
        product_id: int,
        destination: str | Path,
        format_name: str = "Ambos",
    ) -> Path:
        if format_name not in self.FORMATS:
            raise ValueError("El formato de etiqueta no es válido.")
        product = self.products.get_product(product_id)
        if product is None:
            raise ValueError("El producto no existe.")

        output_path = Path(destination)
        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        page_width, page_height = 80 * mm, 50 * mm
        document = canvas.Canvas(
            str(output_path), pagesize=(page_width, page_height)
        )
        document.setTitle(f"Etiqueta {product['codigo']}")
        document.setFont("Helvetica-Bold", 9)
        product_name = str(product["nombre"])
        if len(product_name) > 42:
            product_name = product_name[:39] + "..."
        document.drawCentredString(
            page_width / 2, page_height - 8 * mm, product_name
        )
        document.setFont("Helvetica", 7)
        document.drawCentredString(
            page_width / 2,
            page_height - 12 * mm,
            f"{product['codigo']}  {product['marca'] or ''}",
        )

        barcode_value = product["codigo_barras"] or product["codigo"]
        qr_value = product["codigo_qr"] or product["codigo"]

        if format_name in ("Código de barras", "Ambos"):
            bar_width = 0.32 * mm if format_name == "Ambos" else 0.42 * mm
            barcode = code128.Code128(
                barcode_value,
                barHeight=14 * mm,
                barWidth=bar_width,
                humanReadable=True,
            )
            maximum_width = 50 * mm if format_name == "Ambos" else 70 * mm
            if barcode.width > maximum_width:
                bar_width *= maximum_width / barcode.width
                barcode = code128.Code128(
                    barcode_value,
                    barHeight=14 * mm,
                    barWidth=bar_width,
                    humanReadable=True,
                )
            barcode_x = (
                5 * mm
                if format_name == "Ambos"
                else (page_width - barcode.width) / 2
            )
            barcode.drawOn(document, barcode_x, 7 * mm)

        if format_name in ("Código QR", "Ambos"):
            size = 22 * mm if format_name == "Código QR" else 18 * mm
            qr = QrCodeWidget(qr_value)
            bounds = qr.getBounds()
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            drawing = Drawing(
                size,
                size,
                transform=[size / width, 0, 0, size / height, 0, 0],
            )
            drawing.add(qr)
            qr_x = (
                (page_width - size) / 2
                if format_name == "Código QR"
                else 57 * mm
            )
            renderPDF.draw(drawing, document, qr_x, 6 * mm)

        document.save()
        return output_path
