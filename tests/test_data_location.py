import json
import sqlite3
from pathlib import Path

import pytest

from app.database.data_location import (
    load_data_directory,
    resolve_existing_database,
    save_data_directory,
    validate_data_directory,
)


def test_rejects_installation_directory(tmp_path):
    install = tmp_path / "program"
    install.mkdir()
    with pytest.raises(ValueError):
        validate_data_directory(install / "data", install_dir=install)
    with pytest.raises(ValueError):
        validate_data_directory(tmp_path, install_dir=install)


def test_missing_config_returns_none(tmp_path):
    assert load_data_directory(tmp_path / "missing.json") is None


def test_invalid_config_fails_closed(tmp_path):
    config = tmp_path / "location.json"
    config.write_text("{broken", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_data_directory(config)


def test_cannot_register_nonexistent_database(tmp_path):
    with pytest.raises(FileNotFoundError):
        save_data_directory(tmp_path / "separate", tmp_path / "config.json")


def test_configured_missing_database_never_falls_back(tmp_path, monkeypatch):
    import app.database.data_location as locations
    folder = tmp_path / "removed"
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"data_directory": str(folder)}), encoding="utf-8")
    monkeypatch.setattr(locations, "configuration_file", lambda: config)
    with pytest.raises(FileNotFoundError):
        resolve_existing_database()


def test_migrate_existing_database_preserves_source(tmp_path, monkeypatch):
    import app.database.data_location as locations
    from app.database.data_migration import migrate_existing_database, inspect_database

    install = tmp_path / "install"
    install.mkdir()
    source_folder = install / "data"
    source_folder.mkdir()
    source = source_folder / "echandochal.db"
    with sqlite3.connect(source) as conn:
        for name in ("configuracion", "productos", "ventas", "detalle_venta",
                     "compras", "proveedores"):
            conn.execute(f"CREATE TABLE {name} (id INTEGER)")
        conn.execute("INSERT INTO productos VALUES (1)")
        conn.execute("INSERT INTO ventas VALUES (1)")
    monkeypatch.setattr(locations, "installation_directory", lambda: install)
    # The migration module imports the validation function; override the install root there.
    import app.database.data_migration as migration
    monkeypatch.setattr(migration, "validate_data_directory",
                        lambda path: locations.validate_data_directory(path, install_dir=install))
    config = tmp_path / "config.json"
    monkeypatch.setattr(locations, "configuration_file", lambda: config)
    dest = migrate_existing_database(source, tmp_path / "user-data")
    assert inspect_database(dest) == inspect_database(source)
    assert source.is_file()
    assert locations.load_data_directory() == dest.parent


def test_migration_refuses_to_overwrite_existing_database(tmp_path, monkeypatch):
    import app.database.data_location as locations
    import app.database.data_migration as migration
    install = tmp_path / "program"
    install.mkdir()
    monkeypatch.setattr(locations, "installation_directory", lambda: install)
    monkeypatch.setattr(migration, "validate_data_directory",
                        lambda p: locations.validate_data_directory(p, install_dir=install))
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as conn:
        for name in ("configuracion", "productos", "ventas", "detalle_venta",
                     "compras", "proveedores"):
            conn.execute(f"CREATE TABLE {name} (id INTEGER)")
        conn.execute("INSERT INTO productos VALUES (123)")
    folder = tmp_path / "data"
    folder.mkdir()
    existing = folder / "echandochal.db"
    existing.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        migration.migrate_existing_database(source, folder)
    assert existing.read_bytes() == b"keep"
    assert migration.inspect_database(source)["productos"] == 1


def test_migration_rejects_invalid_source_without_creating_destination(tmp_path, monkeypatch):
    import app.database.data_location as locations
    import app.database.data_migration as migration
    install = tmp_path / "program"
    install.mkdir()
    monkeypatch.setattr(locations, "installation_directory", lambda: install)
    monkeypatch.setattr(migration, "validate_data_directory",
                        lambda p: locations.validate_data_directory(p, install_dir=install))
    source = tmp_path / "echandochal.db"
    source.write_bytes(b"not a sqlite database")
    folder = tmp_path / "target"
    with pytest.raises(sqlite3.DatabaseError):
        migration.migrate_existing_database(source, folder)
    assert source.read_bytes() == b"not a sqlite database"
    assert not (folder / "echandochal.db").exists()

def test_migration_failed_config_save_can_recover_existing_copy(tmp_path, monkeypatch):
    import app.database.data_location as locations
    import app.database.data_migration as migration

    install = tmp_path / "program"
    install.mkdir()
    monkeypatch.setattr(locations, "installation_directory", lambda: install)
    monkeypatch.setattr(migration, "validate_data_directory",
                        lambda p: locations.validate_data_directory(p, install_dir=install))

    source = tmp_path / "old" / "echandochal.db"
    source.parent.mkdir()
    with sqlite3.connect(source) as db:
        for table in ("configuracion", "productos", "ventas", "detalle_venta",
                      "compras", "proveedores"):
            db.execute(f"CREATE TABLE {table} (id INTEGER)")
        db.execute("INSERT INTO productos VALUES (1)")
        db.execute("INSERT INTO ventas VALUES (1)")

    target = tmp_path / "external"
    config = tmp_path / "settings" / "data-location.json"
    monkeypatch.setattr(locations, "configuration_file", lambda: config)

    def fail_to_save(_folder):
        raise OSError("simulated configuration failure")

    monkeypatch.setattr(migration, "save_data_directory", fail_to_save)
    with pytest.raises(OSError, match="simulated"):
        migration.migrate_existing_database(source, target)

    copied = target / "echandochal.db"
    assert copied.is_file()
    assert migration.inspect_database(copied) == migration.inspect_database(source)
    assert not config.exists()

    # Wizard recovery choice registers the already-copied validated database.
    locations.save_data_directory(target)
    assert locations.load_data_directory() == target.resolve()
    assert migration.inspect_database(source)["ventas"] == 1


def test_setup_wizard_exposes_existing_database_recovery():
    source = Path("app/ui/data_setup_dialog.py").read_text(encoding="utf-8")
    assert "Recuperar una base ya copiada" in source
    assert "save_data_directory(folder)" in source
    assert "elif self.recover.isChecked():" in source
