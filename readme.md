# WRO 2026 Future Engineers — Self-Driving Car

**Team:** Sky Flyers (Team #1090)
**Team Leader:** Deepesh Kumar Kotta
**Member 2:** Bade Hari Preetham
**Member 3:** Abhishek K
**Coach:** Saurav Kumar Topo

An autonomous vehicle stack for the [WRO Future Engineers 2026](https://wro-association.org/)
Self-Driving Cars challenge: a Raspberry Pi + Logitech C270 camera on the vehicle, an Arduino
Uno as a real-time motor/servo/sensor co-processor, running both the **Open Challenge**
(three laps, no traffic signs, random inner-wall corridor width) and the **Obstacle
Challenge** (three laps obeying red/green pillar traffic signs, then parallel parking)
as defined in the WRO 2026 Game Rules, §5/§8/§9.

> **Status:** full pipeline is wired end-to-end and runs on synthetic frames in
> `--dry-run` mode (see [Testing](#testing) below). On-track calibration against the
> real camera, lighting, and field geometry is still outstanding — see
> [Known limitations / what's left](#known-limitations--whats-left).

> **For judges / reviewers:** this file is the build/run reference. For the
> design-reasoning narrative scored under WRO Appendix C (mobility, power/sensors,
> software, systems thinking, reproducibility), see
> **[`ENGINEERING_JOURNAL.md`](ENGINEERING_JOURNAL.md)**.

## What it does

- **Capture & pre-processing** — grabs frames from the Logitech C270 (`camera/capture.py`),
  crops a fixed ROI, and applies a bird's-eye perspective warp (`camera/warp.py`) so
  corridor-width and pillar-position math happens in a top-down metric frame instead of
  raw perspective pixels.
- **Colour segmentation** — HSV thresholds for red/green pillars, magenta parking
  markers, and orange/blue corner-boundary lines (`camera/hsv.py`, `config/hsv_config.py`,
  tunable on-site with `hsv_tuner.py`), plus a black mask for corridor/wall detection.
- **Detection**
  - Pillar contours → distance (similar-triangles, `camera/distance.py`) and
    steering-relevant angle/offset (`camera/angle.py`), tracked frame-to-frame by
    centroid (`camera/tracker.py`).
  - Corridor/wall edges → a corridor-centering error signal, with a documented
    single-wall-visible fallback (`camera/corridor.py`) for when only one track
    boundary is in frame — this is what drives the Open Challenge, which has no
    pillars to steer by.
  - Corner boundary lines (orange/blue) for lap/section counting (`camera/lines.py`).
  - Parking-lot magenta markers (`camera/parking.py`).
- **World model** (`world_model/`) — tracks which of the 8 track sections the vehicle is
  in, predicts/corrects traffic-sign "seats" per section (`seat_estimator.py`,
  `obstacle.py`), and maintains lap/section state (`section_observer.py`, `track.py`,
  `world.py`) so the planner always knows where the vehicle is on the field, not just
  what the current frame shows.
- **Planner** (`planner/planner.py`) — an explicit state machine (`WAIT -> OPEN_DRIVE` /
  `OBS_DRIVE -> PARK_SEEK -> PARK_EXEC -> DONE`) that switches steering source between
  pillar-obedience and corridor-centering, triggers the parking hand-off after three
  laps (WRO §9.22), and owns challenge-type selection (`ChallengeType.OPEN` /
  `.OBSTACLE`).
- **Control**
  - PID steering controller (`control/pid.py`).
  - Speed scheduling with cruise/corner/park/stall-floor PWM tiers, ramped rather than
    stepped (`control/speed.py`).
  - Parallel-parking maneuver controller (`control/parking_maneuver.py`).
  - `control/serial_link.py` packages `(steering_deg, speed_pwm, flag)` into the
    `S<steer>,<speed>,<flag>\n` wire protocol and ships it to the Arduino, with an
    automatic mock backend when no hardware is attached and a fail-safe demotion to
    mock if a write ever fails mid-run. Also reads back uplink events (`BTN`, `LINE`,
    `DIST_F=/DIST_L=/DIST_R=<cm>`, `IMU=<deg>`) from the Arduino, non-blocking.
  - `control/proximity.py` — `ParkingCollisionGuard` fuses the front HC-SR04 range with
    the camera's parking-marker apparent width to force-stop before the vehicle
    contacts a parking-lot limitation (WRO §9.24.7).
- **Firmware** (`firmware/vehicle_controller.ino`) — the Arduino Uno counterpart: drives
  the steering servo and single drive motor (a **STH-39D219 NEMA14 stepper**, driven
  STEP/DIR through an A4988/DRV8825-family driver — see [Drive motor](#drive-motor)
  below) from downlink commands, debounces the physical start button and reports it
  upstream (WRO §9.10/§9.11 — one power switch, one start button, no extra
  interactions), reports the backup IR line sensor, pings **three** HC-SR04 sensors
  (front/left/right, round-robin so no single loop() call blocks on more than one)
  for range, and integrates an **MPU-6050** gyro-Z reading into a yaw-heading
  estimate used for parking-heading correction. A watchdog stops the drive motor if
  the Pi goes quiet for >500 ms (USB unplug / vision-loop crash) instead of coasting
  on the last command forever.

### Drive motor

The rear axle is driven by a single **Shinano Kenshi STH-39D219** (NEMA14, 6-wire,
1.8°/step — 200 full steps/rev), wired **bipolar** (the two center-tap wires are left
disconnected) through an **A4988 or DRV8825** STEP/DIR driver module — this replaces
the earlier brushed DC gearmotor + single-channel L298N. Power reaches the axle
through a **20T (motor) → 60T (axle) timing-belt pulley pair** (6 mm belt width,
202 mm belt length), a **3:1 reduction** that trades motor RPM for axle torque —
convert step rate to axle RPM with `axle_rpm = (step_hz / 200) * 60 / 3` (200 = full
steps/rev, 3 = the pulley ratio; see the matching comment next to `STEP_FREQ_MAX_HZ`
in `vehicle_controller.ino`). The wire protocol between the Pi and Arduino is
unchanged
the Pi and Arduino is unchanged (`control/serial_link.py` still sends a 0–100
"PWM-style" speed magnitude); the firmware now maps that magnitude onto a step-pulse
frequency (`STEP_FREQ_MIN_HZ`…`STEP_FREQ_MAX_HZ` in `vehicle_controller.ino`) instead
of an H-bridge duty cycle, and generates the STEP pulses non-blockingly each `loop()`
tick so it never stalls the ultrasonic/IMU/serial servicing. `STEP_FREQ_MAX_HZ`,
`STEPPER_DIR_FORWARD_LEVEL`, and `STEPPER_ENABLE_ACTIVE_LOW` are placeholders like the
HSV ranges elsewhere in this project — recalibrate/verify them against the real
driver board and wheel load before trusting them. Only one stepper axis (one driver,
one motor) is ever wired, so the WRO §11.5/§11.13 "single driven motor" argument is
unchanged from the DC-motor build.
- **Telemetry** — every frame's key state (section, lap, steering, speed, world-model
  summary) is logged to CSV (`utils/telemetry.py`, `logs/`) for later run analysis.

## Project layout

```
main.py                        Entry point: camera -> masks -> detect -> world model
                                -> planner -> steering/speed -> serial -> telemetry
firmware/
  vehicle_controller.ino        Arduino Uno: servo PWM, stepper STEP/DIR drive motor, start button, IR line
                                sensor, 3x HC-SR04 (F/L/R), MPU-6050 yaw, watchdog
camera/
  capture.py                    Logitech C270 (OpenCV VideoCapture) setup
  warp.py                       Bird's-eye perspective warp + corridor width (cm)
  hsv.py, morphology.py         Colour thresholding + mask cleanup
  contours.py, tracker.py       Pillar contour detection + frame-to-frame tracking
  distance.py, angle.py         Pillar distance / steering-angle math
  corridor.py                   Corridor-centering error (Open Challenge + fallback)
  lines.py                      Orange/blue corner-boundary line detection
  parking.py                    Magenta parking-lot marker detection
config/
  hsv_config.py, hsv_ranges.json   Tunable HSV ranges (persisted from hsv_tuner.py)
control/
  pid.py                        PID controller
  speed.py                      Cruise/corner/park PWM scheduling
  serial_link.py                Downlink command packaging + uplink event reads
  parking_maneuver.py           Parallel-parking controller
world_model/
  obstacle.py, seat_estimator.py   Traffic-sign seat prediction/correction
  section_observer.py, track.py   Section/lap tracking, corridor-width holder
  vehicle_state.py, memory.py     State containers
  world.py                        Wires the above into one WorldModel object
planner/
  planner.py                    WAIT/OPEN_DRIVE/OBS_DRIVE/PARK_SEEK/PARK_EXEC/DONE
                                 state machine + challenge-type selection
utils/
  fps.py, telemetry.py          FPS counter, CSV run logger
tests/
  test_camera_math.py            pytest coverage for camera math modules
  test_world_model.py            pytest coverage for world-model modules
hsv_tuner.py                    Interactive on-site HSV recalibration tool
calibrate_focal_length.py       Interactive FOCAL_LENGTH recalibration tool
docs/
  index.html                    Build guide, BOM, wiring reference
  camera_processing.html        Vision-pipeline walkthrough
setup/
  disable_wifi.sh               One-time Pi setup: disables onboard Wi-Fi/BT (WRO §11.10)
cad/
  chassis_placeholder.stl       PLACEHOLDER geometry only -- see cad/README.md
media/
  photos/                       PLACEHOLDER -- vehicle/team photos go here, see media/README.md
  VIDEO_LINKS.md                PLACEHOLDER -- YouTube URLs go here (WRO §7)
ENGINEERING_JOURNAL.md          Design-reasoning narrative, scored under WRO Appendix C
```

## Requirements

- Raspberry Pi (or laptop, for `--dry-run`) + Logitech C270 USB webcam
- Arduino Uno (or compatible) running `firmware/vehicle_controller.ino`
- Python 3.9+, plus:

```bash
pip install -r requirements.txt
```

`camera/capture.py` uses plain OpenCV `VideoCapture`, so `--dry-run` mode runs
identically on a laptop with no camera or Arduino attached.

## Running it

```bash
# Real hardware, Obstacle Challenge (default):
python3 main.py --port /dev/ttyACM0

# Real hardware, Open Challenge:
python3 main.py --port /dev/ttyACM0 --challenge OPEN

# No hardware attached -- synthetic frames + mock serial backend,
# exercises the full pipeline (steering source selection, speed
# scheduling, planner state transitions, corner counting, parking
# hand-off, telemetry) end-to-end:
python3 main.py --dry-run --headless --frames 200
```

Key flags (`python3 main.py --help` for the full list):

| Flag | Purpose |
|---|---|
| `--dry-run` | Synthetic frames + mock serial backend, no hardware required |
| `--headless` | No `cv2.imshow` windows (required for `--dry-run` off-screen/CI use) |
| `--challenge {OPEN,OBSTACLE}` | Select challenge type; deliberately CLI-only rather than a physical selector switch — see the firmware header comment in `vehicle_controller.ino` for why (WRO §9.9/§9.10/§9.11: only power + start-button interactions are permitted) |
| `--port`, `--baud` | Serial port / baud rate for the Arduino link |
| `--mock-serial` | Force the mock serial backend even with a port given |
| `--excluded-color {RED,GREEN}` | Which pillar colour is *not* expected in a given card layout (world-model seat prediction) |
| `--no-telemetry` | Disable CSV logging to `logs/` |
| `--auto-start` | Skip waiting for SPACE/physical button in `--dry-run` |

Press **ESC** (with a display attached) or **SPACE** to start a round manually; on real
hardware the physical Arduino start button (WRO §9.10/§9.11) is what actually starts a
round during competition.

## Calibrating for the real robot

These constants are physical-camera/physical-field calibrations and **cannot be set
correctly from a laptop** — they must be measured on the actual vehicle, camera mount,
and (for lighting) the actual competition venue:

- `camera/distance.py`: `FOCAL_LENGTH` — run `calibrate_focal_length.py` against the
  real C270 at a known pillar distance.
- `camera/angle.py`: `CAMERA_FOV` — measure the real horizontal FOV against the actual
  mount.
- `camera/warp.py`: `WARP_SRC` — mark a real 400x400 mm square on the track floor and
  recalibrate the four corner points for the actual mount height/angle.
- `world_model/seat_estimator.py` — calibrate against the real 1000 mm / 600 mm section
  widths (WRO §8) on a physical or taped-out mock field.
- `control/speed.py`: `CRUISE_PWM` / `CORNER_PWM` / `PARK_PWM` / `MIN_PWM` — starting
  points only; tune on-track against the real drivetrain.
- HSV ranges (`config/hsv_config.py`) — re-run `hsv_tuner.py` under the actual
  competition-venue lighting (WRO §13.18 explicitly calls out lighting-dependent colour
  drift).
- `firmware/vehicle_controller.ino`: `LINE_THRESHOLD` — recalibrate the backup IR line
  sensor's ADC threshold against the real sensor and track surface.
- `control/parking_maneuver.py`: `PARK_HEADING_THRESHOLD_DEG` / `PARK_KP_HEADING` —
  starting points for the MPU-6050 heading-correction term; tune against how much the
  real gyro drifts over one ~3-minute round and how the vehicle actually responds to a
  given steering correction while reversing.
- **Left/right HC-SR04 → corridor fusion** — `camera/corridor.py`'s single-wall-visible
  fallback currently uses only the camera. The left/right ultrasonic readings are
  parsed and available (`main.py`'s `left_distance_cm`/`right_distance_cm`, logged to
  telemetry, shown on the HUD) but are **not yet fused into the corridor-centering
  math** — doing that safely needs the same real corridor-width calibration as the
  fallback constant above, on the physical field, not blindly from a laptop.

Until these are done, the pipeline runs correctly in `--dry-run` but its real-world
accuracy is unverified.

## Testing

```bash
python3 -m pytest tests/
```

`tests/test_camera_math.py` and `tests/test_world_model.py` are `pytest` suites
covering the camera math and world-model modules respectively. Most individual modules
(`serial_link.py`, `speed.py`, `warp.py`, `parking_maneuver.py`, `world.py`, etc.) also
carry a `_run_tests()` self-test runnable directly, e.g. `python3 -m control.serial_link`.

For an end-to-end smoke test without hardware:

```bash
python3 main.py --dry-run --headless --frames 200
```

## Known limitations / what's left

The vision -> world-model -> planner -> control -> serial pipeline is wired end-to-end
and verified against synthetic frames. What's left is physical validation, not missing
code:

1. **On-robot calibration** (see the section above) — focal length, FOV, warp corners,
   seat-estimator geometry, PWM tiers, HSV ranges, and the line-sensor threshold are all
   placeholder starting points until measured on the real vehicle and venue.
2. **Real-track dry runs** — the Open and Obstacle Challenge state machines have not yet
   been validated with a full 3-lap run on a physical track.
3. **Vehicle build verification** — the chassis needs to be checked against
   `docs/index.html`'s claimed BOM/wiring (single drive motor + mechanically linked
   axle, Ackermann steering, no caster/omni wheels, no active wireless per WRO §11.10)
   with photos/build evidence. `setup/disable_wifi.sh` now gives the Wi-Fi/Bluetooth-off
   claim a runnable artifact (run once on the real Pi, `sudo bash setup/disable_wifi.sh`
   then reboot) — but any physical RF module (HC-05/ESP8266/etc.) still has to be
   physically removed from the board by hand; no script can do that.
4. **Competition submission assets** (WRO §7) — vehicle photos (every side, top,
   bottom, team photo) and the two >=30 s autonomous-driving YouTube videos (one per
   challenge) are still needed for GitHub scoring. Placeholder slots and checklists
   now exist for both — see `media/README.md` (photos) and `media/VIDEO_LINKS.md`
   (video URLs) — but the actual media still requires the physical vehicle.
5. **CAD/STL — new chassis in fabrication.** Our competition chassis is being
   custom 3D-printed and is **not yet finished** as of this submission (~15 days
   before competition, in line with WRO §7's final-commit deadline). The design
   files for it are being added to `cad/` directly by the team as they come off
   the printer/CAD tool; `cad/chassis_placeholder.stl` remains as the original
   WRO-max-envelope bounding-box reference until then. Any BOM weight/dimension
   figures elsewhere in this README and `docs/index.html` describe the prior
   interim prototype chassis used to validate the software pipeline, not the
   final competition chassis, unless noted otherwise. Full reasoning and the
   formal timeline are in `ENGINEERING_JOURNAL.md` → Criterion 1 → *"Chassis
   manufacturing status and submission timeline"*, and the current state of
   this folder is tracked in `cad/README.md`.
6. **Hardcopy submission (WRO §7).** In addition to the GitHub repository, a
   hardcopy of the documentation (this README + `ENGINEERING_JOURNAL.md`, or
   an exported PDF of both) must be brought to and submitted at the
   international final. This is a physical/logistics checklist item for
   competition day, not something this repository can satisfy on its own.
7. **Git history** — this repo now has a real, local commit history (`git log`),
   grouped by subsystem. It does **not** satisfy WRO §7's *timing* rule (first
   commit >=2 months before the competition with >=1/5 of the code, second
   >=1 month before, third >=2 weeks before) — those commits have to exist across
   real calendar time, and this history was made in one sitting today. Push this
   to a real GitHub remote now and let your *future* commits (as you wire up the
   hardware items above) establish that real timeline; don't try to backdate these.

## WRO reference

This project targets the **WRO 2026 Future Engineers — Self-Driving Cars** category.
See the official General Rules document (2026 season, version January 15th 2026) for
the authoritative game description, scoring (Appendix C), and vehicle regulations this
codebase is built against.
