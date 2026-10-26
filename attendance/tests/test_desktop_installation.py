"""Desktop installation profile: per-install secrets and data beside the executable."""
from core.config import ensure_installation_secrets


PACKAGED_ENV = (
    "# SRTime Desktop release profile\n"
    "DB_ENGINE=sqlite\n"
    "SECRET_KEY=__GENERATE__\n"
    "TERMINAL_CREDENTIAL_KEY=__GENERATE__\n"
    "# DB_PASS=\n"
)


def _values(path):
    return dict(
        line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.startswith("#")
    )


def test_placeholders_become_unique_keys_and_comments_survive(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(PACKAGED_ENV, encoding="utf-8")

    assert ensure_installation_secrets(env_path) is True

    values = _values(env_path)
    assert values["DB_ENGINE"] == "sqlite"
    assert len(values["SECRET_KEY"]) >= 48 and not values["SECRET_KEY"].startswith("__")
    assert values["TERMINAL_CREDENTIAL_KEY"] != values["SECRET_KEY"]
    assert "# DB_PASS=" in env_path.read_text(encoding="utf-8")


def test_two_installations_from_same_package_get_different_keys(tmp_path):
    first, second = tmp_path / "a.env", tmp_path / "b.env"
    for path in (first, second):
        path.write_text(PACKAGED_ENV, encoding="utf-8")
        ensure_installation_secrets(path)

    assert _values(first)["SECRET_KEY"] != _values(second)["SECRET_KEY"]
    assert _values(first)["TERMINAL_CREDENTIAL_KEY"] != _values(second)["TERMINAL_CREDENTIAL_KEY"]


def test_existing_keys_are_never_rotated(tmp_path):
    # Rotating TERMINAL_CREDENTIAL_KEY would make stored terminal passwords unreadable.
    env_path = tmp_path / ".env"
    env_path.write_text("SECRET_KEY=real-key\nTERMINAL_CREDENTIAL_KEY=real-terminal-key\n", encoding="utf-8")

    assert ensure_installation_secrets(env_path) is False
    assert _values(env_path) == {"SECRET_KEY": "real-key", "TERMINAL_CREDENTIAL_KEY": "real-terminal-key"}


def test_missing_profile_is_left_alone(tmp_path):
    assert ensure_installation_secrets(tmp_path / ".env") is False


def test_frozen_desktop_keeps_data_beside_executable(monkeypatch, tmp_path):
    # PyInstaller runs modules from _internal; SQLite must live beside SRTime_Win.exe,
    # where the installer ships and preserves attendance.db.
    import sys

    from core import config, database

    exe = tmp_path / "SRTime_Win.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", [str(exe)])
    assert config.runtime_root() == tmp_path

    monkeypatch.setattr(database, "base_dir", str(config.runtime_root()))
    url = database.build_database_url({"DB_ENGINE": "sqlite", "SQLITE_DB_PATH": "attendance.db"})
    assert url == f"sqlite:///{tmp_path / 'attendance.db'}"
