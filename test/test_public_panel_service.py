from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from services.public_panel_service import PublicPanelService

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _shanghai_time(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SHANGHAI_TZ)


def test_service_loads_defaults_when_file_missing(tmp_path: Path) -> None:
    with patch.object(PublicPanelService, "_now_shanghai", return_value=_shanghai_time(2026, 4, 22, 8)):
        service = PublicPanelService(tmp_path / "public_panel.json")
        status = service.get_public_status()

    assert status["enabled"] is False
    assert status["mode"] == "daily"
    assert status["available_quota"] == 0
    assert status["quota"] == 0
    assert status["daily_limit"] == 0
    assert status["daily_used"] == 0
    assert status["daily_reset_date"] == "2026-04-22"
    assert status["fixed_quota"] == 0
    assert status["disabled_reason"] == "disabled"


def test_daily_mode_resets_on_next_china_day(tmp_path: Path) -> None:
    with patch.object(PublicPanelService, "_now_shanghai", return_value=_shanghai_time(2026, 4, 22, 10)):
        service = PublicPanelService(tmp_path / "public_panel.json")
        service.update_config(
            enabled=True,
            title="studio",
            description="demo",
            mode="daily",
            daily_limit=5,
            fixed_quota=9,
        )
        reservation = service.reserve_quota(2)
        service.commit_reservation(reservation)

    with patch.object(PublicPanelService, "_now_shanghai", return_value=_shanghai_time(2026, 4, 23, 0, 1)):
        status = service.get_public_status()

    assert status["daily_used"] == 0
    assert status["daily_limit"] == 5
    assert status["daily_reset_date"] == "2026-04-23"
    assert status["available_quota"] == 5
    assert status["disabled_reason"] is None


def test_fixed_mode_reserve_commit_and_release_quota(tmp_path: Path) -> None:
    with patch.object(PublicPanelService, "_now_shanghai", return_value=_shanghai_time(2026, 4, 22, 12)):
        service = PublicPanelService(tmp_path / "public_panel.json")
        service.update_config(
            enabled=True,
            title="studio",
            description="demo",
            mode="fixed",
            daily_limit=7,
            fixed_quota=5,
        )

    reservation = service.reserve_quota(3)
    service.commit_reservation(reservation)

    status = service.get_public_status()
    assert status["mode"] == "fixed"
    assert status["fixed_quota"] == 2
    assert status["available_quota"] == 2
    assert status["quota"] == 2

    release_only = service.reserve_quota(1)
    service.release_reservation(release_only)

    assert service.get_public_status()["fixed_quota"] == 2


def test_add_quota_only_supported_in_fixed_mode(tmp_path: Path) -> None:
    with patch.object(PublicPanelService, "_now_shanghai", return_value=_shanghai_time(2026, 4, 22, 12)):
        service = PublicPanelService(tmp_path / "public_panel.json")
        service.update_config(
            enabled=True,
            title="studio",
            description="demo",
            mode="daily",
            daily_limit=3,
            fixed_quota=0,
        )

    with pytest.raises(ValueError, match="fixed mode"):
        service.add_quota(2)


def test_service_marks_quota_exhausted_when_enabled_but_empty(tmp_path: Path) -> None:
    with patch.object(PublicPanelService, "_now_shanghai", return_value=_shanghai_time(2026, 4, 22, 12)):
        service = PublicPanelService(tmp_path / "public_panel.json")
        service.update_config(
            enabled=True,
            title="studio",
            description="demo",
            mode="fixed",
            daily_limit=0,
            fixed_quota=0,
        )

    status = service.get_public_status()

    assert status["available_quota"] == 0
    assert status["disabled_reason"] == "quota_exhausted"


def test_service_reloads_changes_written_by_another_process(tmp_path: Path) -> None:
    store_file = tmp_path / "public_panel.json"

    with patch.object(PublicPanelService, "_now_shanghai", return_value=_shanghai_time(2026, 4, 22, 12)):
        admin_service = PublicPanelService(store_file)
        public_service = PublicPanelService(store_file)
        admin_service.update_config(
            enabled=True,
            title="共享平台",
            description="demo",
            mode="daily",
            daily_limit=100,
            fixed_quota=0,
        )

    status = public_service.get_public_status()

    assert status["enabled"] is True
    assert status["available_quota"] == 100
    assert status["disabled_reason"] is None
