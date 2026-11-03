"""Exportación de etiquetas por lote en PDF y Word."""
from io import BytesIO
from pathlib import Path

import barcode
import qrcode
from barcode.writer import ImageWriter
from docx import Document
from docx.shared import Inches, Pt
from PIL import Image as PILImage
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.database.connection import Database
from app.services.product_service import ProductService


class LabelService:
    """Crea etiquetas sin modificar códigos ni existencias del inventario."""

    FORMATS = ("Código de barras", "Código QR", "Ambos")
    OUTPUT_TYPES = ("PDF", "Word (.docx)")
    COLS = 2
    ROWS = 5

    def __init__(self, database: Database) -> None:
        self.products = ProductService(database)

    @staticmethod
    def _barcode_image(value: str) -> BytesIO:
        output = BytesIO()
        code = barcode.get("code128", value, writer=ImageWriter())
        code.write(output, options={
            "module_width": 0.22, "module_height": 9,
            "quiet_zone": 2, "font_size": 8, "text_distance": 2,
            "write_text": True, "dpi": 220,
        })
        output.seek(0)
        return output

    @staticmethod
    def _qr_image(value: str) -> BytesIO:
        qr = qrcode.QRCode(box_size=7, border=2)
        qr.add_data(value)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        output = BytesIO()
        image.save(output, format="PNG")
        output.seek(0)
        return output

    def _products_for_labels(self, product_ids: list[int]) -> list[dict]:
        if not product_ids:
            raise ValueError("Selecciona al menos un producto.")
        if len(set(product_ids)) != len(product_ids):
            raise ValueError("La selección tiene productos duplicados.")
        products = []
        for product_id in product_ids:
            product = self.products.get_product(int(product_id))
            if product is None:
                raise ValueError(f"No se encontró el producto {product_id}.")
            products.append(product)
        return products

    @staticmethod
    def _fit_text(text: str, max_width: float, font: str, size: float) -> str:
        if stringWidth(text, font, size) <= max_width:
            return text
        while text and stringWidth(text + "...", font, size) > max_width:
            text = text[:-1]
        return text + "..."

    def _draw_pdf_label(
        self, pdf: canvas.Canvas, product: dict, mode: str,
        x: float, y: float, width: float, height: float,
    ) -> None:
        # x/y: esquina inferior izquierda de cada etiqueta.
        pdf.setLineWidth(0.35)
        pdf.setStrokeColorRGB(0.75, 0.75, 0.75)
        pdf.rect(x + 2 * mm, y + 2 * mm, width - 4 * mm, height - 4 * mm)
        cx = x + width / 2
        name = str(product["nombre"])
        color = str(product.get("color") or "Sin especificar")
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawCentredString(cx, y + height - 9 * mm,
            self._fit_text(name, width - 10 * mm, "Helvetica-Bold", 9))
        pdf.setFont("Helvetica", 8)
        pdf.drawCentredString(cx, y + height - 14 * mm,
            self._fit_text("Color: " + color, width - 10 * mm, "Helvetica", 8))
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(cx, y + height - 18 * mm, str(product["codigo"]))
        bar_value = str(product.get("codigo_barras") or product["codigo"])
        qr_value = str(product.get("codigo_qr") or product["codigo"])
        if mode in ("Código de barras", "Ambos"):
            img = PILImage.open(self._barcode_image(bar_value))
            max_width = min(58 * mm, width - 32 * mm) if mode == "Ambos" else width - 14 * mm
            barcode_width = min(max_width, 0.85 * width)
            barcode_height = 21 * mm
            left = x + 5 * mm if mode == "Ambos" else cx - barcode_width / 2
            pdf.drawImage(ImageReader(img), left, y + 5 * mm,
                          barcode_width, barcode_height, preserveAspectRatio=True,
                          anchor="c")
        if mode in ("Código QR", "Ambos"):
            img = PILImage.open(self._qr_image(qr_value))
            size = 23 * mm if mode == "Código QR" else 21 * mm
            left = cx - size / 2 if mode == "Código QR" else x + width - size - 5 * mm
            pdf.drawImage(ImageReader(img), left, y + 5 * mm, size, size)

    def _generate_pdf(self, products: list[dict], destination: Path, mode: str) -> None:
        page_width, page_height = letter
        pdf = canvas.Canvas(str(destination), pagesize=letter)
        pdf.setTitle("Etiquetas de productos - Echando Chal")
        margin_x = 11 * mm
        margin_y = 10 * mm
        width = (page_width - 2 * margin_x) / self.COLS
        height = (page_height - 2 * margin_y) / self.ROWS
        per_page = self.COLS * self.ROWS
        for index, product in enumerate(products):
            if index and index % per_page == 0:
                pdf.showPage()
            position = index % per_page
            row, col = divmod(position, self.COLS)
            x = margin_x + col * width
            y = page_height - margin_y - (row + 1) * height
            self._draw_pdf_label(pdf, product, mode, x, y, width, height)
        pdf.save()

    def _generate_docx(self, products: list[dict], destination: Path, mode: str) -> None:
        doc = Document()
        section = doc.sections[0]
        section.page_width, section.page_height = Inches(8.5), Inches(11)
        section.top_margin = Inches(0.45)
        section.bottom_margin = Inches(0.45)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)
        style = doc.styles["Normal"]
        style.font.name = "Arial"
        style.font.size = Pt(8)
        for page_start in range(0, len(products), self.COLS * self.ROWS):
            if page_start:
                doc.add_page_break()
            page_products = products[page_start:page_start + self.COLS * self.ROWS]
            table = doc.add_table(rows=self.ROWS, cols=self.COLS)
            table.style = "Table Grid"
            table.autofit = False
            for row in table.rows:
                for cell in row.cells:
                    cell.width = Inches(3.65)
            for index, product in enumerate(page_products):
                row, col = divmod(index, self.COLS)
                cell = table.cell(row, col)
                cell.text = ""
                title = cell.paragraphs[0]
                title.alignment = 1
                title.add_run(str(product["nombre"])).bold = True
                p = cell.add_paragraph()
                p.alignment = 1
                p.add_run("Color: " + str(product.get("color") or "Sin especificar"))
                p = cell.add_paragraph()
                p.alignment = 1
                p.add_run(str(product["codigo"]))
                if mode == "Ambos":
                    p = cell.add_paragraph()
                    p.alignment = 1
                    p.add_run().add_picture(
                        self._barcode_image(str(product.get("codigo_barras") or product["codigo"])),
                        width=Inches(2.15),
                    )
                    p.add_run().add_picture(
                        self._qr_image(str(product.get("codigo_qr") or product["codigo"])),
                        width=Inches(0.78),
                    )
                elif mode == "Código de barras":
                    p = cell.add_paragraph()
                    p.alignment = 1
                    p.add_run().add_picture(
                        self._barcode_image(str(product.get("codigo_barras") or product["codigo"])),
                        width=Inches(2.9),
                    )
                else:
                    p = cell.add_paragraph()
                    p.alignment = 1
                    p.add_run().add_picture(
                        self._qr_image(str(product.get("codigo_qr") or product["codigo"])),
                        width=Inches(1),
                    )
        doc.save(destination)

    def generate_product_labels(
        self,
        product_ids: list[int],
        destination: str | Path,
        format_name: str = "Ambos",
        output_type: str = "PDF",
    ) -> Path:
        if format_name not in self.FORMATS:
            raise ValueError("El contenido de etiqueta no es válido.")
        if output_type not in self.OUTPUT_TYPES:
            raise ValueError("El tipo de archivo no es válido.")
        products = self._products_for_labels(product_ids)
        suffix = ".pdf" if output_type == "PDF" else ".docx"
        output_path = Path(destination).with_suffix(suffix)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_type == "PDF":
            self._generate_pdf(products, output_path, format_name)
        else:
            self._generate_docx(products, output_path, format_name)
        return output_path

    def generate_product_label(
        self, product_id: int, destination: str | Path,
        format_name: str = "Ambos",
    ) -> Path:
        """Conserva las etiquetas individuales tradicionales de 80 x 50 mm."""
        if format_name not in self.FORMATS:
            raise ValueError("El contenido de etiqueta no es válido.")
        product = self._products_for_labels([product_id])[0]
        output_path = Path(destination).with_suffix(".pdf")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        page_width, page_height = 80 * mm, 50 * mm
        pdf = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))
        pdf.setTitle(f"Etiqueta {product['codigo']}")
        self._draw_pdf_label(
            pdf, product, format_name, 0, 0, page_width, page_height
        )
        pdf.save()
        return output_path
