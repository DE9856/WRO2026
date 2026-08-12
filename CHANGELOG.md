# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project does not yet follow Semantic Versioning strictly (pre-1.0,
hardware-in-the-loop prototype) — version numbers below are milestones,
not guarantees of API stability.

## [Unreleased]

### Added
- **Team identification filled in.** `ENGINEERING_JOURNAL.md`, `readme.md`,
  and `docs/index.html` previously had a `[fill in team name / members /
  country]` placeholder in the journal and no team info at all elsewhere.
  Added: Team Sky Flyers (#1090); Team Leader Deepesh Kumar Kotta; Members
  Bade Hari Preetham and Abhishek K; Coach Saurav Kumar Topo.
- **Hardcopy submission requirement documented.** WRO §7 requires a
  physical hardcopy of the documentation at the international final, in
  addition to the GitHub repository. This wasn't mentioned anywhere in the
  repo before. Added as a checklist item to `readme.md` (Known
  limitations), `ENGINEERING_JOURNAL.md` (reproducibility checklist table),
  and `docs/index.html` (§11 GitHub Repository Requirements).
- **Chassis-in-fabrication status formally documented.** The team's
  competition chassis is a custom 3D-printed design still in fabrication
  as of this submission (~15 days before competition, aligned with WRO
  §7's final-commit deadline) and will not be complete by that deadline.
  Added a full explanation — timeline, what's being submitted in its
  place, what happens at vehicle check — to `ENGINEERING_JOURNAL.md`
  (new "Chassis manufacturing status and submission timeline" subsection
  under Criterion 1), with matching shorter notes in `readme.md` (Known
  limitations) and `docs/index.html` (new callout in the Actuation &
  Drive section). `cad/README.md` rewritten to reflect that real STL/CAD
  files are being added by the team directly as fabrication completes,
  rather than describing only the bounding-box placeholder.

### Changed
- **Stale numbers synced in `ENGINEERING_JOURNAL.md`.** The reproducibility
  section still said "25/25 tests passing" and "~13,000 characters" from
  an earlier session; the repo has since grown to 115 passing tests and
  readme.md is now ~17,000 characters. Updated both references (project
  layout comment, reproducibility checklist table, testing-status
  paragraph) to match current reality.
- **Drive motor swapped from brushed DC gearmotor to stepper (STH-39D219).**
  The rear axle is now driven by a single Shinano Kenshi STH-39D219 (NEMA14,
  1.8°/step, 6-wire wired bipolar) through an A4988/DRV8825-family STEP/DIR
  driver, replacing the single-channel L298N + DC gearmotor. `firmware/
  vehicle_controller.ino`: `D4`/`D5`/`D10` are now `STEPPER_DIR`/
  `STEPPER_STEP`/`STEPPER_ENABLE` instead of `L298N IN1`/`IN2`/`ENA`;
  `writeDriveMotor()` now maps the same 0–100 speed magnitude onto a
  step-pulse frequency (`STEP_FREQ_MIN_HZ`…`STEP_FREQ_MAX_HZ`) instead of a
  PWM duty cycle, and a new non-blocking `serviceStepperPulse()` generates
  the STEP square wave each `loop()` tick (no `Stepper.h`/blocking
  `delay()`, so ultrasonic/IMU/serial servicing is never stalled).
  `stopMotor()` now also de-energizes the driver (`STEPPER_ENABLE` idle)
  between commands, since stepper coils draw holding current even when not
  turning. **Unchanged:** the `S<steer>,<speed>,<flag>\n` wire protocol
  between the Pi and Arduino (`control/serial_link.py`, `control/speed.py`)
  — the Pi side needs no code changes, only the Arduino-side interpretation
  of the speed field changed. `docs/index.html`, `readme.md`, and
  `ENGINEERING_JOURNAL.md` updated to match.
- **Documented the belt/pulley reduction**: 20T (motor) → 60T (axle)
  timing belt (6mm width, 202mm belt length — a 3:1 reduction), replacing
  the earlier generic "gearbox" wording in `docs/index.html`'s BOM/wiring
  and `ENGINEERING_JOURNAL.md`'s drivetrain rationale. Added a
  step-frequency → axle-RPM conversion comment next to `STEP_FREQ_MAX_HZ`
  in `firmware/vehicle_controller.ino` for on-track speed tuning. No
  firmware logic change — the ratio only matters for converting motor
  step rate to real-world axle RPM by hand, not for the step-pulse
  generator itself.

- **Stepper driver current-limit calculated and motor-supply battery
  decided** (paper decisions, not yet trimmed/assembled on hardware).
  Motor rated 3.5V/0.7A per phase (nameplate reading); driver board
  identified as a Pololu-footprint DRV8825 clone ("DRV8825 92TC5 A588"),
  assumed 0.1Ω sense resistors per the common convention for that board
  family → Vref = 0.35V. Motor supply (VMOT) moved off the shared 7.4V
  2S LiPo onto a dedicated 4S Li-ion pack (two 2S sub-packs in series,
  ~14.8V nominal) since the DRV8825's 8.2V floor left too little margin
  against LiPo sag on a single 2S rail. `firmware/vehicle_controller.ino`
  header comment and `ENGINEERING_JOURNAL.md` ("Stepper driver
  current-limit calibration", "Drive-motor supply battery") updated with
  the derivation, the calibration procedure, and the risks flagged
  (sense-resistor assumption unverified; two independently-BMS'd
  sub-packs need matched-voltage checks and separate charging; shared
  ground required between the two battery domains).

### Added
- **Placeholders for every remaining hardware-blocked submission asset**,
  clearly labelled as placeholders rather than left as bare gaps:
  - `cad/chassis_placeholder.stl` — a WRO §11.1 max-envelope bounding box
    (300×200×300mm) plus a rough plate placeholder, explicitly **not** a
    real chassis design (see `cad/README.md`).
  - `media/README.md` + `media/photos/` — checklist for the 7 required
    vehicle/team photos (WRO §7), with a specific note on the bottom-view
    shot judges use to check drivetrain compliance.
  - `media/VIDEO_LINKS.md` — placeholder table + recording checklist for
    the two required ≥30s autonomous-driving YouTube clips.
- **Real local git history.** `git init` + 9 commits grouped by subsystem
  (scaffolding, world-model, camera, control/planner, firmware, tests,
  main.py, docs, session docs). Genuine commits, not fabricated — but does
  **not** satisfy WRO §7's commit-timing rule (2mo/1mo/2wk spread), since
  that requires real calendar time; `readme.md`/`docs/index.html`/
  `ENGINEERING_JOURNAL.md` all say so explicitly.
- **Real sensor loadout matched in firmware**: the vehicle carries 3x HC-SR04
  (front/left/right), 1x MPU-6050, 1x IR line sensor, and the camera — but the
  firmware only ever wired one forward HC-SR04 and left the MPU-6050 as an
  unused pin reservation, even though `docs/index.html` already *claimed* MPU
  yaw feedback was active during parking. Rewrote
  `firmware/vehicle_controller.ino` to actually read all three ultrasonic
  sensors (round-robin scheduled so no single `loop()` call blocks on more
  than one `pulseIn()`) and to read the MPU-6050 over bare I2C registers
  (`Wire.h` only, no external library dependency), integrating gyro-Z into a
  yaw heading estimate sent as `IMU=<deg>`. Uplink protocol changed from a
  single `DIST=<cm>` to `DIST_F=`/`DIST_L=`/`DIST_R=<cm>`; `main.py` accepts
  both the new and legacy formats.
- **C.13 fix**: `control/parking_maneuver.py`'s `ParkingManeuver` only ever
  zeroed horizontal pixel error against the parking markers, with no way to
  confirm the vehicle was actually parallel to the wall (WRO §1.8.2's real
  requirement; §10's scoring table gives 0 of 15 points for "not parallel").
  Added a second proportional term against `heading_error_deg` — the
  MPU-6050 yaw delta since `PARK_EXEC` began (reference heading captured in
  `main.py` the instant parking execution starts). "Centered" now requires
  both pixel error AND heading error within threshold for the same number of
  consecutive frames. Falls back to the original pixel-only behaviour if no
  IMU reading is available (no MPU-6050 wired/detected, or `--dry-run`).
- `utils/telemetry.py`: logs `dist_front_cm`/`dist_left_cm`/`dist_right_cm`/
  `imu_heading_deg` per frame; `main.py`'s HUD overlay shows them live.

### Fixed
- **C.14**: parking-lot markers had no real proximity/collision sensing —
  `planner.parking_marker_touched()` existed and `control/parking_maneuver.py`
  even had a comment citing WRO §9.24.7, but nothing ever called it. Added
  `control/proximity.py`'s `ParkingCollisionGuard`, which trips on either (1)
  the HC-SR04 forward range (`DIST=<cm>`, now parsed in `main.py`'s uplink
  loop — previously received but silently dropped) dropping below a
  near-contact threshold, or (2) a magenta marker's apparent width filling
  too much of the ROI (catches lateral contact the forward-facing ultrasonic
  can't see). Debounced over consecutive frames to reject single-frame
  ultrasonic noise; wired into `main.py`'s `PARK_EXEC` loop to force-stop via
  `planner.parking_marker_touched()` the moment either cue trips.

### Remaining before competition
- On-robot calibration: `FOCAL_LENGTH`, `CAMERA_FOV`, `WARP_SRC`, seat-estimator
  section widths, `control/speed.py` PWM tiers, HSV ranges under venue lighting,
  and the firmware `LINE_THRESHOLD` — all currently placeholder starting points
  (see readme.md → *Calibrating for the real robot*).
- Full 3-lap dry runs on a physical Open Challenge and Obstacle Challenge track.
- Vehicle build verification against `docs/index.html`'s claimed BOM/chassis
  (photos/build evidence not yet captured).
- Competition submission assets (WRO §7): vehicle photos, team photo, and one
  >=30s autonomous-driving YouTube video per challenge.

## [0.3.0] — Full pipeline wired end-to-end

### Added
- `firmware/vehicle_controller.ino` — Arduino Uno firmware implementing the
  `S<steer_deg>,<speed_pwm>,<flag>\n` downlink protocol, `BTN` start-button
  uplink (debounced), `LINE` backup lap-sensor uplink, and `DIST=<cm>` HC-SR04
  range uplink. Implements the WRO §9.10/§9.11 physical start procedure (one
  power switch, one momentary start button) and a >500 ms command-timeout
  watchdog that stops the drive motor if the Pi goes quiet mid-round.
- `control/serial_link.py`: `SerialLink.read_events()` — non-blocking uplink
  read, wired into `main.py`'s main loop so `BTN` starts a round on real
  hardware and `LINE` is received (currently intentionally not actioned by the
  planner — see `main.py`'s uplink-handling comment for the reasoning).
- `world_model/` fully wired into `main.py`: `WorldModel`, `SectionObserver`,
  `Track`, and `VehicleState` now drive real per-frame section/lap tracking
  instead of only being exercised by a standalone demo script.
- `planner/planner.py`: full `WAIT -> OPEN_DRIVE`/`OBS_DRIVE -> PARK_SEEK ->
  PARK_EXEC -> DONE` state machine, switching steering source between
  corridor-centering (Open Challenge) and pillar-obedience + world-model
  mapping (Obstacle Challenge), and triggering the parking hand-off after
  three completed laps (WRO §9.22).
- `camera/corridor.py` — corridor-centering error signal (with a single-wall
  fallback) so the Open Challenge, which has no pillars, has a steering
  source.
- `camera/warp.py` — bird's-eye perspective warp + corridor-width-in-cm
  helper, so downstream geometry (corridor centering, seat estimation) works
  in real-world units instead of raw perspective pixels.
- `camera/lines.py` — orange/blue corner-boundary line detection for
  lap/section counting.
- `camera/parking.py` + `control/parking_maneuver.py` — magenta parking-marker
  detection and a parallel-parking maneuver controller.
- `control/speed.py` — cruise/corner/park/stall-floor PWM scheduling, ramped
  rather than stepped between tiers.
- `utils/telemetry.py` — per-frame CSV logging of section/lap/steering/speed/
  world-model state to `logs/` for run analysis.
- `tests/test_camera_math.py` — pytest coverage for the camera math modules
  (previously untested).
- `main.py --dry-run` — synthetic-frame + mock-serial mode that exercises the
  complete pipeline (steering source selection, speed scheduling, planner
  state transitions, corner-boundary counting, parking hand-off, telemetry)
  end-to-end without any hardware attached.
- `main.py --challenge {OPEN,OBSTACLE}` CLI flag for selecting challenge type
  (a physical selector switch was deliberately not added — see the firmware
  header comment for the WRO §9.9 reasoning).

### Changed
- Switched camera capture from `picamera2` (Raspberry Pi Camera Module,
  ~54° FOV) to plain OpenCV `VideoCapture` against a Logitech C270
  (~60° FOV, subject to on-track recalibration).

## [0.1.0] — Initial vision + steering prototype

### Added
- Raspberry Pi camera capture pipeline, fixed ROI crop for a 640x480 source.
- HSV-based colour thresholding for red and green pillars.
- Morphological mask cleanup — open then close — to suppress noise before
  contour detection.
- Contour-based pillar detection with an aspect-ratio filter (tall, not wide)
  to reject floor reflections, plus per-detection distance estimate via the
  similar-triangles formula.
- Frame-to-frame centroid tracking so steering follows one consistent pillar
  rather than jumping between detections.
- Steering-angle and clearance-offset error calculation.
- PID controller with proper `dt`-based integral and derivative terms.
- Live HUD overlay: steering value, FPS counter, pillar bounding
  boxes/centroids/distance, and per-mask debug windows.
- Interactive HSV tuner script with trackbars for on-site recalibration.
- Scaffolding for a world model — `Obstacle`, `VehicleState`, `Track`,
  `MemoryManager`, `WorldModel` — exercised at this stage only by a
  standalone manual demo script, not yet connected to `main.py`.
- Empty `planner/` package reserved for the lap/section/challenge state
  machine added in 0.3.0.

### Known limitations at this stage (resolved in 0.3.0 unless noted above)
- No throttle/speed output and no serial/motor-controller link.
- No steering source when no pillar is visible (blocked Open Challenge).
- `world_model` package not wired into the main loop.
- `planner/planner.py` contained no logic.
- Only red/green were detected; no parking-marker or corner-line colours.
- No automated test coverage for the camera math modules.
