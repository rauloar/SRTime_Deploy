"""Regression coverage for addon discovery in a PyInstaller onefile package."""

from services import addons


def test_enabled_addon_loads_without_a_physical_addons_directory(monkeypatch):
    monkeypatch.setenv("SRTIME_ENABLED_ADDONS", "sundial")
    monkeypatch.setattr(addons.os, "listdir", lambda _path: (_ for _ in ()).throw(FileNotFoundError()))
    monkeypatch.setattr(addons.os.path, "exists", lambda _path: False)
    addons.clear_addon_cache()
    try:
        available = addons.get_available_addons()
    finally:
        addons.clear_addon_cache()

    assert "Sundial ERTeckno" in available
    assert available["Sundial ERTeckno"]["is_parser"] is True
