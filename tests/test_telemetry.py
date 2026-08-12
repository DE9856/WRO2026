"""
tests/test_telemetry.py
WRO 2026 Future Engineers — pytest cases for utils/telemetry.py.

H.28 FIX: converted from telemetry.py's in-module _run_tests() into
real pytest test_* functions (using the tmp_path fixture instead of a
hand-rolled tempfile.mkdtemp()/shutil.rmtree() pair). No functional
change.
"""

import csv
import os

from utils.telemetry import TelemetryLogger


def test_logger_writes_header_and_one_row_per_log_call(tmp_path):
    log = TelemetryLogger(log_dir=str(tmp_path), filename="test.csv")
    log.log(planner_state="OBS_DRIVE", lap=1, section=2, steering_deg=5.5, speed_pwm=40.0)
    log.log(planner_state="OBS_DRIVE", lap=1, section=2, steering_deg=-3.0, speed_pwm=42.0)
    log.close()

    path = os.path.join(str(tmp_path), "test.csv")
    assert os.path.exists(path)
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 2, rows
    assert rows[0]["planner_state"] == "OBS_DRIVE"
    assert rows[0]["frame"] == "1"
    assert rows[1]["frame"] == "2"


def test_disabled_logger_is_safe_noop(tmp_path):
    disabled = TelemetryLogger(log_dir=str(tmp_path), enabled=False)
    disabled.log(planner_state="X")  # must not raise even though disabled
    disabled.close()


def test_unknown_kwargs_are_ignored_rather_than_raising(tmp_path):
    log2 = TelemetryLogger(log_dir=str(tmp_path), filename="unknown_kwarg.csv")
    log2.log(planner_state="OBS_DRIVE", made_up_field_xyz=123)  # must not raise
    log2.close()
