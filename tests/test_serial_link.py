"""
tests/test_serial_link.py
WRO 2026 Future Engineers — pytest cases for control/serial_link.py.

H.28 FIX: converted from serial_link.py's in-module _run_tests() into
real pytest test_* functions. No functional change.
"""

from control.serial_link import SerialLink


def test_forced_mock_backend_accepts_sends_and_formats_wire_protocol():
    link = SerialLink(force_mock=True, verbose_mock=False)
    assert link.is_mock()
    ok = link.send(steering_deg=5.5, speed_pwm=40.0, state_flag="D")
    assert ok is True
    assert len(link._backend.sent) == 1
    assert link._backend.sent[0] == b"S5.50,40.0,D\n"
    link.close()


def test_unopenable_real_port_falls_back_to_mock():
    link2 = SerialLink(port="/dev/ttyDOES_NOT_EXIST_9999", verbose_mock=False)
    assert link2.is_mock(), "an unopenable port must fall back to MOCK, not raise"
    link2.send(0, 0, "S")


def test_min_send_interval_throttles_rapid_sends():
    link3 = SerialLink(force_mock=True, verbose_mock=False, min_send_interval=10.0)
    first = link3.send(0, 0, "D")
    second = link3.send(1, 1, "D")  # immediately after -- should be throttled
    assert first is True
    assert second is False
    assert len(link3._backend.sent) == 1, "throttled call must not reach the backend"


def test_negative_speed_pwm_round_trips_through_protocol():
    link4 = SerialLink(force_mock=True, verbose_mock=False)
    link4.send(steering_deg=-12.3, speed_pwm=-20.0, state_flag="P")
    assert link4._backend.sent[0] == b"S-12.30,-20.0,P\n"


def test_close_never_raises_on_mock_backend():
    link = SerialLink(force_mock=True, verbose_mock=False)
    link.close()  # must not raise


def test_read_events_on_mock_backend_returns_empty_list():
    link6 = SerialLink(force_mock=True, verbose_mock=False)
    assert link6.read_events() == []
