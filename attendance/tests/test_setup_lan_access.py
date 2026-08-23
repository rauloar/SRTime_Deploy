"""Regression coverage for safe LAN access during initial setup."""
from api.routers.setup import _is_authorized_setup_host


def test_setup_allows_private_lan_without_listing_each_client(monkeypatch):
    monkeypatch.setenv("SRTIME_SETUP_ALLOWED_IPS", "private")
    assert _is_authorized_setup_host("192.168.1.25")
    assert _is_authorized_setup_host("10.10.0.18")
    assert not _is_authorized_setup_host("8.8.8.8")


def test_setup_supports_cidr_range(monkeypatch):
    monkeypatch.setenv("SRTIME_SETUP_ALLOWED_IPS", "172.20.50.0/24")
    assert _is_authorized_setup_host("172.20.50.8")
    assert not _is_authorized_setup_host("172.20.51.8")
