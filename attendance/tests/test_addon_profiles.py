"""Profiles control which ingestion capabilities SRTime exposes."""

from services import addons


def test_sundial_profile_exposes_terminal_management_and_tm_mr001_import(monkeypatch):
    monkeypatch.setenv("SRTIME_ENABLED_ADDONS", "sundial")
    addons.clear_addon_cache()
    try:
        available = addons.get_available_parsers()
    finally:
        addons.clear_addon_cache()

    assert list(available) == ["Sundial ERTeckno"]
    features = available["Sundial ERTeckno"]["ui_features"]
    assert features["file_import"] is True
    assert features["terminal_management"] is True
    assert features["network_import"] is True
    assert features["file_extensions"] == [".txt"]
    assert features["file_name_patterns"] == ["TM-MR001.txt"]


def test_zkteco_profile_exposes_terminal_management_and_native_usb_import(monkeypatch):
    monkeypatch.setenv("SRTIME_ENABLED_ADDONS", "zkteco")
    addons.clear_addon_cache()
    try:
        available = addons.get_available_parsers()
    finally:
        addons.clear_addon_cache()

    assert list(available) == ["ZKTeco"]
    features = available["ZKTeco"]["ui_features"]
    assert features["file_import"] is True
    assert features["terminal_management"] is True
    assert features["network_import"] is True
    assert features["file_extensions"] == [".dat"]
    assert features["file_name_patterns"] == ["att.dat"]


def test_every_terminal_driver_declares_terminal_ui(monkeypatch):
    """Un driver sin ui_features escondería la pestaña Terminales en Web y Desktop."""
    monkeypatch.delenv("SRTIME_ENABLED_ADDONS", raising=False)
    addons.clear_addon_cache()
    try:
        available = addons.get_available_parsers()
    finally:
        addons.clear_addon_cache()

    drivers = {name: info for name, info in available.items() if info["is_driver"]}
    assert drivers
    for name, info in drivers.items():
        assert info["ui_features"].get("terminal_management") is True, name
        assert info["ui_features"].get("network_import") is True, name


def test_enabled_ui_features_follow_the_profile(monkeypatch):
    monkeypatch.setenv("SRTIME_ENABLED_ADDONS", "sundial")
    addons.clear_addon_cache()
    try:
        features = addons.enabled_ui_features()
    finally:
        addons.clear_addon_cache()

    assert features == {"file_import": True, "network_import": True, "terminal_management": True}


def test_enabled_ui_features_without_addons(monkeypatch):
    monkeypatch.setattr(addons, "get_available_addons", lambda: {})

    assert addons.enabled_ui_features() == {
        "file_import": False, "network_import": False, "terminal_management": False,
    }
