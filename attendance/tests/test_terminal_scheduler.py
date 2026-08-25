from datetime import date, datetime, time, timedelta

from models.terminal import DeviceTerminal
from services.terminal_scheduler import _inside_window, schedule_next_pull
from services.terminals import public_connection_params


def test_schedule_next_pull_uses_configured_interval():
    terminal = DeviceTerminal(pull_interval_minutes=15)
    now = datetime(2026, 7, 26, 10, 0, 0)

    schedule_next_pull(terminal, now)

    assert terminal.next_pull_at == now + timedelta(minutes=15)


def test_schedule_window_accepts_overnight_period():
    terminal = DeviceTerminal(pull_window_start=time(22, 0), pull_window_end=time(6, 0))

    assert _inside_window(terminal, datetime(2026, 7, 26, 23, 0)) is True
    assert _inside_window(terminal, datetime(2026, 7, 27, 5, 0)) is True
    assert _inside_window(terminal, datetime(2026, 7, 27, 12, 0)) is False


def test_weekly_schedule_uses_selected_day_and_time():
    terminal = DeviceTerminal(
        pull_schedule_mode="weekly",
        pull_schedule_weekdays=[0, 2],  # lunes y miércoles
        pull_schedule_time=time(8, 30),
    )

    schedule_next_pull(terminal, datetime(2026, 7, 26, 10, 0))  # domingo

    assert terminal.next_pull_at == datetime(2026, 7, 27, 8, 30)


def test_weekly_schedule_respects_calendar_end_date():
    terminal = DeviceTerminal(
        pull_schedule_mode="weekly",
        pull_schedule_weekdays=[0],
        pull_schedule_time=time(8, 30),
        pull_schedule_start_date=date(2026, 7, 27),
        pull_schedule_end_date=date(2026, 7, 26),
    )

    schedule_next_pull(terminal, datetime(2026, 7, 26, 10, 0))

    assert terminal.next_pull_at is None


def test_remote_agent_token_is_never_exposed_in_public_terminal_data():
    terminal = DeviceTerminal(connection_params={
        "agent_url": "https://agent.example.test",
        "remote_terminal_id": "north-1",
        "api_token": "enc:secret",
    })

    assert public_connection_params(terminal) == {
        "agent_url": "https://agent.example.test",
        "remote_terminal_id": "north-1",
    }
