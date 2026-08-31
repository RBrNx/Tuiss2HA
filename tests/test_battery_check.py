from unittest.mock import AsyncMock, MagicMock, patch

import datetime
import pytest

from custom_components.tuiss2ha.hub import TuissBlind


def _make_blind(mock_hass) -> TuissBlind:
    fake_device = MagicMock()
    fake_device.name = "TB-01"
    with patch("custom_components.tuiss2ha.hub.bluetooth.async_ble_device_from_address", return_value=fake_device):
        hub = MagicMock()
        hub._hass = mock_hass
        return TuissBlind("AA:BB:CC:DD:EE:FF", "Test", hub)


# _battery_check_due() is the single gate shared by every automatic
# battery-check trigger (see its own docstring in hub.py) — these test it
# directly rather than through async_move_cover's full orchestration, since
# the actual check now runs from the post-move background task
# (hass.async_create_task), which a plain MagicMock hass never executes.


def test_battery_check_due_when_never_checked(mock_hass):
    """No last check recorded and an interval is configured -> due."""
    tb = _make_blind(mock_hass)
    tb._battery_check_days = 1
    tb._last_battery_check = None

    assert tb._battery_check_due() is True


def test_battery_check_due_when_older_than_config(mock_hass):
    """Last check older than the configured interval -> due."""
    tb = _make_blind(mock_hass)
    tb._battery_check_days = 1
    tb._last_battery_check = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)

    assert tb._battery_check_due() is True


def test_battery_check_not_due_when_recent(mock_hass):
    """Last check within the configured interval -> not due."""
    tb = _make_blind(mock_hass)
    tb._battery_check_days = 7
    tb._last_battery_check = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)

    assert tb._battery_check_due() is False


def test_battery_check_not_due_when_disabled(mock_hass):
    """_battery_check_days == 0 (feature disabled) -> never due, regardless of age."""
    tb = _make_blind(mock_hass)
    tb._battery_check_days = 0
    tb._last_battery_check = None

    assert tb._battery_check_due() is False


@pytest.mark.asyncio
async def test_post_move_battery_check_runs_when_due(mock_hass):
    """_post_move_battery_check() queries the blind when a check is due."""
    tb = _make_blind(mock_hass)
    tb._battery_check_days = 1
    tb._last_battery_check = None
    tb.get_battery_status = AsyncMock()

    await tb._post_move_battery_check()

    assert tb.get_battery_status.called


@pytest.mark.asyncio
async def test_post_move_battery_check_skipped_when_not_due(mock_hass):
    """_post_move_battery_check() does nothing if the interval hasn't elapsed."""
    tb = _make_blind(mock_hass)
    tb._battery_check_days = 7
    tb._last_battery_check = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    tb.get_battery_status = AsyncMock()

    await tb._post_move_battery_check()

    assert not tb.get_battery_status.called


@pytest.mark.asyncio
async def test_post_move_battery_check_skipped_when_flag_set(mock_hass):
    """_post_move_battery_check(skip_battery_check=True) never queries, even if due."""
    tb = _make_blind(mock_hass)
    tb._battery_check_days = 1
    tb._last_battery_check = None
    tb.get_battery_status = AsyncMock()

    await tb._post_move_battery_check(skip_battery_check=True)

    assert not tb.get_battery_status.called
