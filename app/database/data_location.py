"""Ubicación persistente de datos. No migra ni crea bases automáticamente."""
from __future__ import annotations

import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys

CONFIG_NAME = "data-location.json"
DB_NAME = "echandochal.db"


def configuration_file() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise RuntimeError("No se encontró LOCALAPPDATA en Windows.")
    sandbox = getattr(sys, "frozen", False) and (installation_directory() / "sandbox-mode.ini").is_file()
    app_folder = "EchandoChalPOS-Sandbox" if sandbox else "EchandoChalPOS"
    return Path(base) / app_folder / CONFIG_NAME


def installation_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _is_inside(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def validate_data_directory(folder: str | Path, install_dir: Path | None = None) -> Path:
    path = Path(folder).expanduser().resolve()
    install = (install_dir or installation_directory()).resolve()
    if _is_inside(path, install) or _is_inside(install, path):
        raise ValueError("La carpeta de datos debe ser independiente de la instalación.")
    if path == Path(path.anchor):
        raise ValueError("Seleccione una subcarpeta dedicada, no la raíz del disco.")
    return path


def load_data_directory(config_path: Path | None = None) -> Path | None:
    config = config_path or configuration_file()
    if not config.exists():
        return None
    try:
        value = json.loads(config.read_text(encoding="utf-8"))
        directory = value["data_directory"]
        if not isinstance(directory, str) or not directory.strip():
            raise ValueError("Ruta vacía")
        return validate_data_directory(directory)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("La configuración de datos es inválida; no se creará una base nueva.") from exc


def save_data_directory(folder: str | Path, config_path: Path | None = None) -> Path:
    """Guarda una ruta SOLO si ya existe una base SQLite íntegra en ella."""
    directory = validate_data_directory(folder)
    database = directory / DB_NAME
    if not database.is_file():
        raise FileNotFoundError(f"No existe una base de datos en: {database}")
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("La base no superó la validación de integridad.")
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"productos", "ventas", "detalle_venta", "configuracion"} <= tables:
            raise RuntimeError("La base no corresponde a Echando Chal POS.")
    config = config_path or configuration_file()
    config.parent.mkdir(parents=True, exist_ok=True)
    temp = config.with_suffix(".tmp")
    temp.write_text(json.dumps({"data_directory": str(directory)}, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(config)
    return database


def resolve_existing_database() -> Path:
    """Nunca crea una base nueva en una ubicación no configurada."""
    configured = load_data_directory()
    if configured is not None:
        db = configured / DB_NAME
        if not db.is_file():
            raise FileNotFoundError(f"No se encontró la base configurada: {db}")
        return db
    legacy = installation_directory() / "data" / DB_NAME
    if legacy.is_file():
        return legacy
    raise FileNotFoundError(
        "No se encontró la base de datos. Configure la ubicación antes de iniciar."
    )
