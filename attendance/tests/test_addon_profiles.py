"""Profiles control which ingestion capabilities SRTime exposes."""

from services import addons


def test_sundial_profile_only_exposes_file_import(monkeypatch):
    monkeypatch.setenv("SRTIME_ENABLED_ADDONS", "sundial")
    addons.clear_addon_cache()
    try:
        available = addons.get_available_parsers()
    finally:
        addons.clear_addon_cache()

    assert list(available) == ["Sundial ERTeckno"]
    features = available["Sundial ERTeckno"]["ui_features"]
    assert features["file_import"] is True
    assert features["terminal_management"] is False
    assert features["network_import"] is False
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
