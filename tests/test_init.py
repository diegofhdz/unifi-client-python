"""Tests for the unifi_client package initialization."""

import unifi_client


def test_version() -> None:
    """Test that the package version is defined."""
    assert unifi_client.__version__ == "0.1.0"
