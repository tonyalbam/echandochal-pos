"""Reinicio EXCLUSIVO de la base ficticia de pruebas de Cobro Mixto.

USO (PowerShell; cerrar la aplicación antes):
    $env:LOCALAPPDATA = "D:\\EchandoChalPOS_Perfil_CobroMixto"
    .\\.venv\\Scripts\\python.exe tools\\reset_test_database.py --confirmar

No acepta rutas alternativas y jamás modifica la base de producción.
Antes de sustituir la base de pruebas deja un respaldo íntegro.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.schema import create_database

TEST_PROFILE = Path(r"D:\EchandoChalPOS_Perfil_CobroMixto")
TEST_FOLDER = Path(r"D:\EchandoChalPOS_CobroMixto_Prueba")
PRODUCTION_FOLDER = Path(r"D:\EchandoChalPOS_Datos")
DATABASE_NAME = "echandochal.db"
REQUIRED_TABLES = {"productos", "ventas", "compras", "configuracion"}


def same_path(left, right):
    if not left or not right:
        return False
    return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(
        os.path.normpath(str(right))
    )


def verify_test_target():
    """Falla cerrado si el perfil o el destino no son los de pruebas."""
    profile = os.environ.get("LOCALAPPDATA")
    if not same_path(profile, TEST_PROFILE):
        raise RuntimeError(
            "LOCALAPPDATA no corresponde al perfil aislado de pruebas. "
            "No se modificó ninguna base de datos."
        )
    config = TEST_PROFILE / "EchandoChalPOS" / "data-location.json"
    if not config.is_file():
        raise RuntimeError(f"No existe la configuración de pruebas: {config}")
    try:
        configured = json.loads(config.read_text(encoding="utf-8"))["data_directory"]
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise RuntimeError("Configuración del perfil de pruebas inválida.") from exc
    if not same_path(configured, TEST_FOLDER):
        raise RuntimeError(
            "El perfil no apunta a la base ficticia permitida. "
            f"Carpeta actual: {configured!r}. No se modificó nada."
        )
    if (
        same_path(TEST_FOLDER, PRODUCTION_FOLDER)
        or same_path(TEST_FOLDER.resolve(), PRODUCTION_FOLDER.resolve())
    ):
        raise RuntimeError("Destino de pruebas coincide con producción.")
    db = TEST_FOLDER / DATABASE_NAME
    if same_path(db.resolve(), (PRODUCTION_FOLDER / DATABASE_NAME).resolve()):
        raise RuntimeError("La base de pruebas apunta a la base de producción.")
    if not db.is_file():
        raise FileNotFoundError(f"No existe la base de pruebas: {db}")
    return db


def check_database(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError(f"La base no pasó integrity_check: {path}")
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not REQUIRED_TABLES <= tables:
            raise RuntimeError(f"La base no corresponde a Echando Chal POS: {path}")


def create_blank_staging(path):
    """Crea la base nueva sin alterar la configuración de ubicación."""
    class LocalDb:
        def __init__(self, connection):
            self.connection = connection

        def cursor(self):
            return self.connection.cursor()

        def commit(self):
            return self.connection.commit()

    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        create_database(LocalDb(connection))
        connection.commit()
    check_database(path)


def reset_test_database():
    if os.name != "nt":
        raise RuntimeError("Este reinicio solo está permitido en Windows.")
    db = verify_test_target()
    check_database(db)

    # Crear ambos archivos fuera del nombre que usa la aplicación.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backups = db.parent / "respaldos_reinicio_pruebas"
    backups.mkdir(parents=True, exist_ok=True)
    backup = backups / f"echandochal_pruebas_antes_reinicio_{stamp}.db"
    archived_original = backups / f"echandochal_pruebas_original_{stamp}.db"
    staged = db.parent / f".echandochal_nueva_{stamp}.db"

    try:
        # Exigir un checkpoint completo. Si existe un proceso bloqueando
        # el WAL, interrumpir en lugar de perder movimientos pendientes.
        with closing(sqlite3.connect(db, timeout=1)) as source:
            checkpoint = source.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint and checkpoint[0] != 0:
                raise RuntimeError(
                    "La base está ocupada. Cierra Echando Chal POS de pruebas."
                )
            with closing(sqlite3.connect(backup)) as target:
                source.backup(target)
        check_database(backup)
        create_blank_staging(staged)

        # Nunca dejar WAL de la base antigua asociado a la nueva.
        sidecars = (Path(str(db) + "-wal"), Path(str(db) + "-shm"))
        for sidecar in sidecars:
            if sidecar.exists():
                raise RuntimeError(
                    f"Hay un archivo SQLite en uso: {sidecar}. "
                    "Cierra la aplicación de pruebas antes de reiniciar."
                )

        db.replace(archived_original)
        try:
            staged.replace(db)
        except Exception:
            archived_original.replace(db)
            raise

        check_database(db)
        return backup, db
    finally:
        if staged.exists():
            staged.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Reinicia solamente la base ficticia de Cobro Mixto."
    )
    parser.add_argument(
        "--confirmar", action="store_true",
        help="Autoriza explícitamente el reinicio de la base de pruebas."
    )
    args = parser.parse_args()
    if not args.confirmar:
        parser.error(
            "Falta --confirmar. No se realizó ninguna modificación."
        )
    try:
        backup, db = reset_test_database()
    except Exception as error:
        print(f"REINICIO CANCELADO: {error}", file=sys.stderr)
        return 1
    print("Base de PRUEBAS reiniciada correctamente.")
    print(f"Nueva base vacía: {db}")
    print(f"Copia segura del contenido anterior: {backup}")
    print("Base de producción: SIN MODIFICACIONES.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
