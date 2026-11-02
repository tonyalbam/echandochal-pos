import json
import sqlite3

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
