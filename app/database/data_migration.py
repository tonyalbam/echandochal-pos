"""Migración transaccional y creación controlada de bases de Echando Chal POS."""
from __future__ import annotations

from datetime import datetime
from contextlib import closing
from pathlib import Path
import sqlite3

from app.database.data_location import DB_NAME, save_data_directory, validate_data_directory


REQUIRED_TABLES = {"configuracion", "productos", "ventas", "detalle_venta", "compras"}


def inspect_database(path: Path) -> dict[str, int]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("La base de origen no supera integrity_check.")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not REQUIRED_TABLES <= tables:
            raise RuntimeError("La base no tiene las tablas requeridas.")
        return {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in ("productos", "ventas", "compras", "proveedores")}


def migrate_existing_database(source: str | Path, target_folder: str | Path) -> Path:
    source = Path(source).resolve()
    folder = validate_data_directory(target_folder)
    destination = folder / DB_NAME
    if not source.is_file():
        raise FileNotFoundError(f"No existe la base original: {source}")
    if source == destination:
        raise ValueError("La ubicación nueva debe ser diferente de la original.")
    before = inspect_database(source)
    folder.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"La base de destino ya existe: {destination}")

    # Copia consistente que incluye transacciones WAL confirmadas.
    temp = folder / ("echandochal_migracion_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".tmp")
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(temp)) as copy:
                original.backup(copy)
        after = inspect_database(temp)
        if before != after:
            raise RuntimeError("Los conteos de la copia no coinciden con el origen.")
        temp.rename(destination)
        # La configuración se publica únicamente después de verificar la copia.
        save_data_directory(folder)
        return destination
    finally:
        if temp.exists():
            temp.unlink()


def initialize_new_database(target_folder: str | Path) -> Path:
    """Solo se utiliza cuando el usuario elige explícitamente instalación nueva."""
    folder = validate_data_directory(target_folder)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / DB_NAME
    if destination.exists():
        raise FileExistsError(f"Ya existe una base en: {destination}")
    from app.database.schema import create_database

    # Crear una base nueva sin pasar por Database(), que exige una base existente.
    class InitialDatabase:
        def __init__(self, connection):
            self.connection = connection
        def cursor(self):
            return self.connection.cursor()
        def commit(self):
            return self.connection.commit()

    try:
        with closing(sqlite3.connect(destination)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            create_database(InitialDatabase(db))
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("La base inicial no pasó integrity_check.")
        save_data_directory(folder)
        return destination
    except Exception:
        # No borrar archivos existentes; solo retirar el archivo creado aquí.
        if destination.exists():
            destination.unlink()
        raise
