from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.database.connection import Database
from app.services.configuration_service import ConfigurationService
from app.services.sale_history_service import SaleHistoryService


class TicketService:
    """Genera comprobantes PDF para ventas registradas."""

    WIDTH = 80 * mm
    MARGIN = 8 * mm

    def __init__(self, database: Database) -> None:
        self.database = database
        self.sale_history = SaleHistoryService(database)
        self.configuration = ConfigurationService(database)

    @staticmethod
    def _wrap_text(text: str, max_width: float) -> list[str]:
        words = str(text).split()
        if not words:
            return [""]

        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if stringWidth(candidate, "Helvetica", 8) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def generate_sale_ticket(
        self,
        sale_id: int,
        destination: str | Path,
    ) -> Path:
        sale = self.sale_history.get_sale(sale_id)
        if sale is None:
            raise ValueError("La venta no existe.")

        output_path = Path(destination)
        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        content_width = self.WIDTH - (2 * self.MARGIN)
        wrapped_items = [
            (item, self._wrap_text(item["nombre"], content_width))
            for item in sale["items"]
        ]
        items_height = sum(
            31 + (len(lines) * 10)
            for _, lines in wrapped_items
        )

        logo_path = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "logo_ticket.png"
        )
        logo: ImageReader | None = None
        logo_width = 0.0
        logo_height = 0.0

        whatsapp_path = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "whatsapp.png"
        )
        whatsapp_icon = (
            ImageReader(str(whatsapp_path))
            if whatsapp_path.is_file()
            else None
        )

        if logo_path.is_file():
            logo = ImageReader(str(logo_path))
            image_width, image_height = logo.getSize()
            scale = min(
                (62 * mm) / image_width,
                (35 * mm) / image_height,
            )
            logo_width = image_width * scale
            logo_height = image_height * scale

        if logo is not None:
            page_height = max(170 * mm, (140 * mm) + items_height)
        else:
            page_height = max(135 * mm, (105 * mm) + items_height)

        document = canvas.Canvas(
            str(output_path),
            pagesize=(self.WIDTH, page_height),
        )
        document.setTitle(f"Ticket {sale['folio']}")

        center = self.WIDTH / 2
        y = page_height - (6 * mm)
        business_name = self.configuration.get_business_name()

        if logo is not None:
            y -= logo_height
            document.drawImage(
                logo,
                center - (logo_width / 2),
                y,
                width=logo_width,
                height=logo_height,
                preserveAspectRatio=True,
                mask="auto",
            )
            y -= 12
            document.setFont("Helvetica-Bold", 10)
            document.drawCentredString(center, y, business_name)
            y -= 14
        else:
            document.setFont("Helvetica-Bold", 14)
            document.drawCentredString(center, y, business_name)
            y -= 15

        document.setFont("Helvetica", 8)
        document.drawCentredString(center, y, "COMPROBANTE DE VENTA")
        y -= 16

        right_edge = self.WIDTH - self.MARGIN
        document.setFont("Helvetica", 8)
        document.drawRightString(
            right_edge,
            y,
            "Plaza Navarra Local 51",
        )
        y -= 11
        document.drawRightString(
            right_edge,
            y,
            "Franccionamiento Los viñedos",
        )
        y -= 12

        phone = "771 112 5462"
        phone_width = stringWidth(phone, "Helvetica", 8)
        if whatsapp_icon is not None:
            icon_size = 4 * mm
            document.drawImage(
                whatsapp_icon,
                right_edge - phone_width - icon_size - 3,
                y - 3,
                width=icon_size,
                height=icon_size,
                preserveAspectRatio=True,
                mask="auto",
            )
        document.drawRightString(right_edge, y, phone)
        y -= 16

        document.setFont("Helvetica", 7)
        document.drawRightString(
            right_edge,
            y,
            "Nombre:____________________________________",
        )
        y -= 11
        document.drawRightString(
            right_edge,
            y,
            "Teléfono: ____________________________________",
        )
        y -= 17

        if sale["cancelada"]:
            document.setFillColor(HexColor("#B91C1C"))
            document.setFont("Helvetica-Bold", 11)
            document.drawCentredString(center, y, "VENTA CANCELADA")
            document.setFillColor(HexColor("#000000"))
            y -= 16

        document.setFont("Helvetica", 8)
        document.drawString(self.MARGIN, y, f"Folio: {sale['folio']}")
        y -= 11
        document.drawString(
            self.MARGIN,
            y,
            f"Fecha: {sale['fecha']}  {sale['hora']}",
        )
        y -= 11
        document.drawString(
            self.MARGIN,
            y,
            f"Pago: {sale['metodo_pago']}",
        )
        y -= 12
        document.line(self.MARGIN, y, self.WIDTH - self.MARGIN, y)
        y -= 13

        for item, name_lines in wrapped_items:
            document.setFont("Helvetica-Bold", 8)
            for line in name_lines:
                document.drawString(self.MARGIN, y, line)
                y -= 10

            document.setFont("Helvetica", 8)
            quantity = float(item["cantidad"])
            unit_price = float(item["precio_unitario"])
            subtotal = float(item["subtotal"])
            document.drawString(
                self.MARGIN,
                y,
                f"{quantity:g} x ${unit_price:,.2f}",
            )
            document.drawRightString(
                self.WIDTH - self.MARGIN,
                y,
                f"${subtotal:,.2f}",
            )
            y -= 16

        document.line(self.MARGIN, y, self.WIDTH - self.MARGIN, y)
        y -= 14

        totals = (
            ("Subtotal", sale["subtotal"]),
            ("Descuento", sale["descuento"]),
            ("Total", sale["total"]),
        )
        for label, value in totals:
            document.setFont(
                "Helvetica-Bold" if label == "Total" else "Helvetica",
                10 if label == "Total" else 8,
            )
            document.drawString(self.MARGIN, y, label)
            document.drawRightString(
                self.WIDTH - self.MARGIN,
                y,
                f"${float(value):,.2f}",
            )
            y -= 13

        y -= 5
        document.setFont("Helvetica", 8)
        document.drawCentredString(center, y, "Gracias por tu compra")
        y -= 17
        document.setFont("Helvetica-Bold", 8)
        document.drawCentredString(
            center,
            y,
            "NO HAY CAMBIOS NI DEVOLUCIONES",
        )
        document.save()

        return output_path
