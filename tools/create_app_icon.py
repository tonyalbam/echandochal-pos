"""Genera el ícono Windows multiresolución desde el logo PNG transparente.

El PNG es la fuente única: se incluye en Qt y el .ico generado se incrusta
en el ejecutable Windows por PyInstaller.
"""
from pathlib import Path

from PIL import Image


ICON_DIR = Path(__file__).resolve().parents[1] / "app" / "assets"
SOURCE = ICON_DIR / "echandochal_icon.png"
DESTINATION = ICON_DIR / "echandochal_icon.ico"


def build_icon(source: Path = SOURCE, destination: Path = DESTINATION) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"No se encontró el logo de Echando Chal: {source}")
    with Image.open(source) as logo:
        if logo.mode not in ("RGBA", "P"):
            raise ValueError("El logo debe ser PNG transparente.")
        icon = logo.convert("RGBA")
        if icon.getchannel("A").getextrema()[0] == 255:
            raise ValueError("El logo debe contener transparencia para el ícono.")
        icon = icon.resize((256, 256), Image.Resampling.LANCZOS)
        icon.save(
            destination,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                   (128, 128), (256, 256)],
        )
    if destination.stat().st_size < 1024:
        raise ValueError("El ícono Windows parece estar incompleto.")
    return destination


if __name__ == "__main__":
    print(build_icon())
