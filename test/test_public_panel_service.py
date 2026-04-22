from __future__ import annotations

from pathlib import Path

from services.public_panel_service import PublicPanelService


def test_service_loads_defaults_when_file_missing(tmp_path: Path) -> None:
    service = PublicPanelService(tmp_path / "public_panel.json")

    status = service.get_public_status()

    assert status["enabled"] is False
    assert status["quota"] == 0
    assert status["title"] == ""
    assert status["description"] == ""


def test_service_reserve_commit_and_release_quota(tmp_path: Path) -> None:
    service = PublicPanelService(tmp_path / "public_panel.json")
    service.update_config(enabled=True, quota=5, title="studio", description="demo")

    reservation = service.reserve_quota(3)
    service.commit_reservation(reservation)

    status = service.get_public_status()
    assert status["quota"] == 2

    release_only = service.reserve_quota(1)
    service.release_reservation(release_only)

    assert service.get_public_status()["quota"] == 2
