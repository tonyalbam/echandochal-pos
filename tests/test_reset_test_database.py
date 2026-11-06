"""El reinicio de prueba nunca debe tocar una base o perfil distinto."""
import json
import os
import sqlite3
from contextlib import closing

import pytest

from tools import reset_test_database as reset


def setup_sandbox(tmp_path, monkeypatch):
    profile = tmp_path / "perfil-prueba"
    folder = tmp_path / "datos-prueba"
    folder.mkdir()
    (profile / "EchandoChalPOS").mkdir(parents=True)
    config = profile / "EchandoChalPOS" / "data-location.json"
    config.write_text(
        json.dumps({"data_directory": str(folder)}), encoding="utf-8"
    )
    monkeypatch.setattr(reset, "TEST_PROFILE", profile)
    monkeypatch.setattr(reset, "TEST_FOLDER", folder)
    monkeypatch.setattr(reset, "PRODUCTION_FOLDER", tmp_path / "production")
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    return folder / "echandochal.db", config


def test_reset_is_rejected_without_test_profile(tmp_path, monkeypatch):
    db, _ = setup_sandbox(tmp_path, monkeypatch)
    reset.create_blank_staging(db)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "otro-perfil"))
    with pytest.raises(RuntimeError, match="no corresponde"):
        reset.verify_test_target()
    assert db.is_file()


def test_reset_is_rejected_if_config_points_to_production(tmp_path, monkeypatch):
    db, config = setup_sandbox(tmp_path, monkeypatch)
    reset.create_blank_staging(db)
    production = tmp_path / "production"
    production.mkdir()
    config.write_text(
        json.dumps({"data_directory": str(production)}), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="no apunta"):
        reset.verify_test_target()
    assert db.is_file()


@pytest.mark.skipif(os.name != "nt", reason="Solo reinicio de Windows")
def test_reset_clears_only_sandbox_and_keeps_verified_backup(tmp_path, monkeypatch):
    db, config = setup_sandbox(tmp_path, monkeypatch)
    reset.create_blank_staging(db)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(
            """INSERT INTO productos(codigo,nombre,precio,existencia)
               VALUES ('PRUEBA1','Ficticio',30,7)"""
        )
        conn.execute(
            """INSERT INTO proveedores(nombre) VALUES ('Proveedor ficticio')"""
        )
        conn.execute(
            """INSERT INTO cierres_caja(
                   fecha, saldo_inicial_centavos, ventas_efectivo_centavos,
                   gastos_centavos, saldo_esperado_centavos, saldo_contado_centavos)
               VALUES ('2026-11-05', 0, 0, 0, 0, 0)"""
        )
        conn.commit()
    original_config = config.read_text(encoding="utf-8")
    backup, recreated = reset.reset_test_database()
    assert recreated == db
    assert backup.is_file()
    assert config.read_text(encoding="utf-8") == original_config
    reset.check_database(db)
    reset.check_database(backup)
    with sqlite3.connect(db) as new_conn:
        assert new_conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0] == 0
        assert new_conn.execute("SELECT COUNT(*) FROM proveedores").fetchone()[0] == 0
        assert new_conn.execute("SELECT COUNT(*) FROM cierres_caja").fetchone()[0] == 0
    with sqlite3.connect(backup) as old_conn:
        assert old_conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0] == 1
        assert old_conn.execute("SELECT COUNT(*) FROM proveedores").fetchone()[0] == 1
        assert old_conn.execute("SELECT COUNT(*) FROM cierres_caja").fetchone()[0] == 1
