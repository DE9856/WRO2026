# Engineering Journal — WRO 2026 Future Engineers Self-Driving Car

**Category:** WRO Future Engineers 2026 — Self-Driving Cars
**Team Name:** Sky Flyers
**Team Number:** 1090
**Team Leader:** Deepesh Kumar Kotta
**Member 2:** Bade Hari Preetham
**Member 3:** Abhishek K
**Coach:** Saurav Kumar Topo
**Document purpose:** This journal is written to WRO's Appendix C rubric —
five criteria, each judged on the *clarity and depth of engineering
reasoning, the quality of testing and iteration, and the reproducibility
of the system*, not on visual polish. `docs/index.html` is our build
reference (BOM, wiring, quick-start); this document is the narrative a
judge should read to understand *why* the vehicle is built the way it is.

> **Honesty note, read first:** As of this document, the vehicle has been
> validated in software only — a 25-case automated `pytest` suite and a
> full synthetic end-to-end `--dry-run` of the entire pipeline (camera →
> world model → planner → control → serial). It has **not yet** been
> tested on a physical chassis, camera, or track. Every claim below is
> scoped honestly: what is implemented and tested in software is marked
> as such; what still requires physical calibration is marked as pending,
> with the specific step needed to close it. See `readme.md` → *"Known
> limitations / what's left"* for the authoritative, current list.

---

## Criterion 1 — Mobility and Mechanical Design

### Drivetrain choice and why

WRO §11.3–§11.5 rule out the simplest mobile-robot base (differential
drive, one motor per side) outright, and §11.4 rules out omni/caster
wheels. That leaves front-wheel, rear-wheel, or four-wheel drive with a
**mechanically linked** driving axle and a **separate steering
actuator**. We chose **rear-wheel drive with Ackermann front steering**:

- **Single NEMA14 stepper motor (Shinano Kenshi STH-39D219)** drives the
  rear axle through a **20T (motor) → 60T (axle) timing-belt reduction**
  (6 mm belt width, 202 mm belt length — a 3:1 speed reduction / torque
  multiplication) — both rear wheels are mechanically forced to turn
  together off the single belt-driven axle shaft. This was a deliberate
  simplification over four-wheel drive: it removes any possibility of
  the two rear wheels being driven at different speeds (which is exactly
  the "electronic differential" WRO §11.5 disqualifies), at the cost of
  some traction on tight corners.
  - *Revision note:* the build started with a brushed DC gearmotor +
    single-channel L298N. We switched to the STH-39D219 stepper for
    open-loop, drift-free speed control — a step-pulse frequency maps
    directly and repeatably to shaft RPM (no current-sense or encoder
    feedback needed), which the DC motor could only approximate via PWM
    duty cycle under a load- and battery-voltage-dependent curve. The
    trade-off is lower peak torque per gram than a comparable DC
    gearmotor, and holding torque draws current even when stationary
    unless the driver is explicitly disabled between commands (which
    `vehicle_controller.ino::stopMotor()` now does).
  - *Why the 3:1 belt reduction:* a NEMA14 stepper's bare-shaft holding
    torque is modest next to the DC gearmotor it replaced (see the
    revision note above), so the 20T→60T pulley pair recovers roughly
    3× shaft torque at the axle (before belt/bearing losses) in exchange
    for 3× lower axle RPM at a given step rate — the same
    torque-for-speed trade a DC gearmotor's internal gearbox would have
    made, just external and swappable (re-pulley to retune the ratio
    without touching the motor or firmware). Motor-shaft step rate →
    axle RPM: `axle_rpm = (step_hz / 200) * 60 / 3` (200 = full
    steps/rev at 1.8°/step, 3 = the pulley ratio) — see the matching
    comment in `firmware/vehicle_controller.ino` next to
    `STEP_FREQ_MAX_HZ`.
- **Wired through a single A4988/DRV8825-family STEP/DIR driver** — only
  STEP, DIR, and ENABLE are connected; the motor's two center-tap wires
  are left disconnected (bipolar wiring) and no second driver or motor is
  present on the harness. This is a hardware-level guarantee, not just a
  firmware promise: even a firmware bug could not accidentally drive a
  second motor channel independently, because there is no second
  channel to drive. We considered a unipolar ULN2003 driver instead, but
  preferred the STEP/DIR interface's simpler timing model (one pulse
  train instead of a 4-phase sequencing table) and higher torque
  available from bipolar drive — a judge inspecting the wiring during
  the vehicle check (§12.6/§12.7) should be able to see compliance
  directly in the harness, not have to trust the code.
- **Two standard rubber wheels on an Ackermann linkage** up front, no
  caster or ball wheel anywhere on the vehicle (§11.4).

### Size/weight budget as a design constraint

§11.1/§11.2 cap the vehicle at 300×200×300 mm and 1.5 kg. This drove two
concrete component decisions: a single drive motor instead of a
dual-motor layout (halves motor+ESC mass for a small traction cost), and
keeping the Pi + Arduino as the only two controllers on board rather than
adding a third board for camera pre-processing — the extra board would
have bought marginal latency headroom at a real weight and mounting-space
cost that the 300×200 mm footprint made hard to justify. Final BOM weight
is currently an estimate, not yet a measured value (see *Testing status*
below).

### Chassis manufacturing status and submission timeline

The competition vehicle uses a custom 3D-printed chassis rather than an
off-the-shelf RC platform, to allow exact control over camera-mount
geometry, sensor placement, and the 300×200×300 mm / 1.5 kg envelope
discussed above. As of this documentation submission, the new chassis is
**in fabrication and not yet complete.**

WRO §7 requires the final GitHub commit no later than two weeks before
the competition, and this submission is being made on that schedule
(approximately 15 days before competition day). The print/assembly of
the new chassis will not be finished within that window — completion is
expected to fall between this submission and the competition itself.
This is disclosed here explicitly rather than presented as finished:

- The **design files** for the new chassis (STL, and source CAD where
  applicable) are included in `cad/` as of this submission, replacing
  the earlier bounding-box placeholder (`cad/chassis_placeholder.stl`).
  These are the real, final-intent design files being sent to the
  printer — the files are complete even though the physical print is
  still in progress. See `cad/README.md` for exactly what is and isn't
  in that folder as of this submission.
- Any BOM weight, dimension figures, or build photos referenced
  elsewhere in this journal and in `docs/index.html` at the time of this
  submission describe the **prior/interim prototype chassis** used to
  develop and validate the vision and control pipeline — not the final
  competition chassis — unless a later note says otherwise.
- The vehicle presented at the official vehicle check (WRO §12.6–§12.9)
  on competition day will be the completed, 3D-printed chassis. Per
  §9.9, the physical/mechanical adjustments involved in finishing
  assembly are not the same as entering data to a program, and are
  expected as normal build completion, not a rules concern.
- We will re-verify dimensions, weight, and BOM accuracy against the
  finished chassis and update this journal and `docs/index.html`
  accordingly once it's built — after the scored commit deadline, so
  that specific update won't itself be scored, but we consider it good
  engineering practice and necessary for our own vehicle-check
  preparation regardless.

Appendix C's Reproducibility criterion (Criterion 5) explicitly rewards
honestly scoping what is and isn't finished rather than penalizing an
open item disclosed clearly, which is the intent of this section.

### Testing status

- **Done (software/paper):** Component selection reviewed against every
  relevant WRO clause (§11.1–§11.5, §11.13) — see the rules-matrix table
  in `docs/index.html`. Wiring harness for the single stepper-axis
  (A4988/DRV8825 STEP/DIR) configuration is fully specified down to the
  pin.
- **Pending (physical):** The interim prototype chassis has been used to
  validate the software pipeline but not yet weighed on a scale. The new
  3D-printed chassis (see *Chassis manufacturing status* above) is still
  in fabrication as of this submission. `docs/index.html`'s BOM weight
  (~1.35 kg estimated) is a datasheet-derived estimate, not a scale
  reading, for either chassis version — called out explicitly rather
  than presented as measured. Once the final chassis is assembled, the
  vehicle must be weighed and measured against the 300×200×300 mm /
  1.5 kg limits before the first vehicle check (`PUNCHLIST_STATUS.md`
  item A.3 / E.18–21).

---

## Criterion 2 — Power and Sensor Architecture

### Power rail separation — a real design decision, not a default

The system uses **two independent step-down regulators** off one 7.4 V
2S LiPo: one 5 V rail for the Pi + Arduino logic, one 6 V rail dedicated
to the steering servo. This was chosen specifically because a shared
logic/servo rail lets a hard steering transient (the servo drawing a
current spike mid-turn) sag the voltage feeding the Raspberry Pi — on a
vision pipeline, a brief brownout there is a full frame-processing stall
at exactly the moment the vehicle is turning, i.e. the worst possible
time to lose steering input. Splitting the rails trades one extra
regulator (cost, weight, wiring) for removing that failure mode
entirely.

### Stepper driver current-limit calibration

The STH-39D219 is rated **3.5 V DC, 0.7 A/phase** (read off the motor's
own nameplate — no authoritative datasheet exists for this exact suffix,
since Shinano Kenshi reused the STH-39D prefix across a family spanning
4.1–30 Ω and 6.8–12+ V). The driver board in hand is a Pololu-footprint
DRV8825 breakout marked `DRV8825 92TC5 A588` — the same design sold
throughout the RAMPS/RepRap 3D-printer ecosystem, which universally uses
**0.1 Ω sense resistors**. We are trusting that convention rather than
measuring the SMD resistors directly (a firm confirmation would require
lifting a leg or reading `R100` off the resistor body under magnification).

```
Vref = I_limit x 5 x R_sense   (DRV8825 formula)
Vref = 0.7 x 5 x 0.1
Vref = 0.35 V
```

Procedure: power the driver (logic + motor supply) with the motor itself
disconnected, black probe to GND, red probe to the trim-pot wiper, adjust
until the wiper reads 0.35 V. Then connect the motor and check case
temperature after a minute of running before trusting the setting
long-term. **Risk flagged and accepted knowingly:** if this board turns
out to use 0.05 Ω sense resistors instead of the assumed 0.1 Ω, 0.35 V
would command ~1.4 A — double the motor's rating — so the first power-up
is done watching/feeling the motor closely rather than left unattended,
as a live sanity check on the 0.1 Ω assumption.

### Drive-motor supply battery

The DRV8825's motor-supply spec is 8.2–45 V. A single 7.4 V nominal 2S
LiPo (the same pack feeding the logic/servo regulators above) sags well
below 8 V for a meaningful fraction of a 3-minute round as it discharges
— borderline-to-below the driver's floor, which risks brownout resets on
the stepper mid-run. Decision: the stepper driver's VMOT is fed from a
**separate 4S Li-ion pack**, built from two 2S sub-packs wired in series
(14.8 V nominal, ~16.8 V full charge, ~12 V at typical 3.0 V/cell
cutoff) — comfortably clear of the driver's 8.2 V floor across the whole
discharge curve, with headroom to spare under the 45 V ceiling.

Caveats accepted with this choice, to revisit once the two packs are in
hand and can be tested together:

- **Charging:** the two 2S sub-packs must always be split apart and
  charged individually through their own balance leads on a 2S-profile
  charger — never charge the series-combined 4S string through one port,
  since neither pack's BMS is aware of the other.
- **Pack matching:** the two sub-packs have independent BMS units that
  don't communicate; if they drift out of balance across charge cycles,
  cell voltages should be checked as roughly matched before each
  competition run rather than assumed.
- **Common ground:** the Arduino's GND, the DRV8825 driver's logic GND,
  and this 4S pack's GND must all be tied together even though VMOT and
  the 5 V/6 V logic/servo rails come from separate batteries — STEP/DIR/
  ENABLE are logic-level signals referenced to a shared ground, not an
  isolated one.
- **Fusing:** a fuse or PTC on the 4S pack's positive lead, given the
  higher voltage now feeding the driver directly (no regulator in the
  path to limit a wiring-fault fault current).

This is a paper decision, not yet validated on hardware — see *Testing
status* below.

### Sensor selection, and why each one is there (not just what it is)

| Sensor | Role | Why this one, specifically |
|---|---|---|
| Logitech C270 (USB webcam) | Primary lane/wall/pillar/parking-marker vision | Originally speced as a Raspberry Pi Camera Module V2; switched to a USB UVC webcam mid-project (see `CHANGELOG.md` 0.3.0) so `camera/capture.py` uses plain OpenCV `VideoCapture` instead of `picamera2` — this decouples the vision pipeline from Pi-specific camera APIs, at the cost of a different (and currently unmeasured) FOV that must be recalibrated (`camera/angle.py::CAMERA_FOV`). |
| 3× HC-SR04 (front/left/right) | Wall-proximity slowdown, parking-marker collision guard, corridor-fallback data | The original design (see `Overall_Guide1.html`) speced **one** forward sensor. We deliberately added left/right units because a single forward sensor cannot detect *lateral* wall proximity during Open Challenge cornering, and cannot see a parking marker the vehicle drifts into sideways while still centering (see `control/proximity.py`'s two-cue design, below). The cost is real: three sensors round-robin-pinged from one Arduino means each individual sensor is only refreshed roughly every 3× the round-robin interval, not every loop — a deliberate throughput/coverage trade-off, documented in the firmware header. |
| MPU-6050 (I²C) | Yaw heading during parking | Added specifically because pixel-centering alone (WRO §1.8.2 / §10 scoring) cannot tell whether the vehicle is *parallel* to the wall — only whether it's centered. WRO's own scoring table gives 15/15 points for parallel-and-centered vs 7/15 for centered-but-not-parallel; a pixel-only controller structurally cannot chase that other 8 points because it has no signal for heading error at all. |
| IR line sensor (analog) | Backup lap-line / corner-boundary detection | Redundant to the camera's orange/blue corner-line detection (`camera/lines.py`) by design — the uplink event is received and logged, but *deliberately not wired into planner logic as an authoritative signal* (see Criterion 4 for why). |

### Iteration evidence (not just the final state)

The firmware's sensor support is not what it looked like at project
start. `CHANGELOG.md` shows the real progression:

- **0.1.0:** camera pipeline only, no sensor uplink at all.
- **0.3.0:** firmware added `DIST=<cm>` (one HC-SR04) and a `BTN` start
  signal, but the MPU-6050 pin was reserved and unused, and
  `docs/index.html` was already (incorrectly) claiming MPU yaw feedback
  was active — a real doc/reality mismatch caught and only fixed this
  session.
- **Unreleased (this session):** firmware rewritten for all three
  HC-SR04s (round-robin scheduled so a single `loop()` call never blocks
  on more than one `pulseIn()`), and a real bare-I²C MPU-6050 driver
  (gyro-Z integrated into a yaw estimate) replacing the unused pin
  comment. Uplink protocol changed from single `DIST=` to
  `DIST_F=`/`DIST_L=`/`DIST_R=`/`IMU=`, with `main.py` accepting both the
  new and legacy formats for backward compatibility.

### Testing status

- **Done (software):** `control/proximity.py`'s `ParkingCollisionGuard`
  (two independent cues — HC-SR04 forward range AND marker apparent
  width — either one alone trips a stop) is unit-tested and exercised in
  `--dry-run`. `control/parking_maneuver.py`'s heading-correction term is
  covered by 4 passing unit tests (fallback-to-pixel-only behaviour when
  no IMU is present, and the combined pixel+heading behaviour when it
  is).
- **Pending (physical):** every numeric constant in this section —
  `FOCAL_LENGTH`, `CAMERA_FOV`, HSV ranges, the IR line sensor's ADC
  threshold, and the left/right HC-SR04 → corridor-centering fusion — is
  a placeholder that must be measured against the real camera, sensors,
  and venue lighting (WRO §13.18 explicitly notes colour drift under
  real lighting). This is deliberate: `camera/corridor.py`'s left/right
  fusion is intentionally left unwired rather than guessed at, because
  blending an untested distance threshold into active steering without a
  way to verify it against a real corridor risks steering the vehicle
  into a wall with high confidence rather than low. The plumbing (uplink
  parsing, telemetry logging, HUD display) is done; only the final
  control-loop wire-in is deferred, and specifically *why* it's deferred
  is documented at the point of deferral (`readme.md` → *Calibrating for
  the real robot*).
- **Pending (physical, driver/battery):** the DRV8825 Vref (0.35 V,
  assuming 0.1 Ω sense resistors) has been calculated but not yet
  measured/trimmed on the physical board, and the 4S Li-ion motor-supply
  pack (two 2S sub-packs in series) has not yet been assembled or tested
  under load. See *Stepper driver current-limit calibration* and
  *Drive-motor supply battery* above for the specific numbers and the
  risks flagged at each decision.

---

## Criterion 3 — Software Architecture and Obstacle Strategy

### Pipeline shape

```
capture → warp (bird's-eye) → HSV segmentation → contour detection
        → centroid tracking → world model (section/seat memory)
        → planner (state machine) → steering-source selection
        → PID / speed scheduling → serial → Arduino
```

Every stage is a separate, independently testable module (`camera/`,
`world_model/`, `planner/`, `control/`) rather than one monolithic loop.
This was a deliberate choice so that `main.py --dry-run` could exercise
the *entire* decision pipeline — steering-source selection, world-model
updates, planner state transitions, speed scheduling, serial output — on
synthetic frames with no hardware attached, rather than only being
testable end-to-end on the real robot.

### Constrained-state obstacle strategy — the actual reasoning, not just the label

WRO's Obstacle Challenge does not place traffic signs arbitrarily: each
straightforward section holds one of a closed set of **36 predefined
configurations** (WRO Figure 8c). We took this as a hard constraint on
the design of the vision/reasoning layer: rather than building a general
open-set object-detection-and-tracking system, `world_model/obstacle.py`
hand-transcribes the real 36-card catalog from Figure 8c
(`CARD_CATALOG`, asserted at import time to contain exactly cards 1–36
with valid seat values) and `Deck`/`match_config` turn a partially-
observed seat vector into the set of *legal* remaining candidates. This
is a genuinely different problem than "detect an obstacle" — it's "which
of the 36 legal states is this," which is a much smaller and more
robust classification problem, and it degrades gracefully: a
low-confidence or partial observation still narrows the candidate set
instead of committing to a wrong answer.

`world_model/section_observer.py` sits between per-frame classification
and this catalog matching: because a single frame almost never sees an
entire section at once (the section is 600–1000 mm long and the camera
is forward-facing), it accumulates per-frame seat votes across the whole
time the vehicle is in a section and only finalizes one seat vector when
the planner signals the section has ended — a deliberate vote-then-commit
design to avoid one noisy frame corrupting the whole section's read.

### State machine — and why it's leaner than our own original plan

Our early planning docs (`Overall_Guide1.html` §07) sketched a six-state
machine: `WAIT → LOCALIZE → MAP_BUILD → PREDICTIVE_DRIVE → PARK_SEEK →
PARK_EXEC → DONE`, with three separate lap-based phases (explore/map,
validate, aggressive-speed-run). The implemented machine
(`planner/planner.py`) is `WAIT → OPEN_DRIVE|OBS_DRIVE → PARK_SEEK →
PARK_EXEC → DONE`. We collapsed `LOCALIZE`/`MAP_BUILD`/`PREDICTIVE_DRIVE`
into a single `OBS_DRIVE` state because, once `SectionObserver` and
`WorldModel` exist as always-on accumulators rather than phase-gated
behaviours, there was no actual decision logic left that depended on
which lap the vehicle was on — section/seat memory accumulates and
corrects itself continuously regardless of lap number, so a separate
"exploration" vs "validation" *state* would have been bookkeeping with
no behavioural difference. This is a case where the as-built design is
simpler than the original plan because the simpler design turned out to
be sufficient, not because the harder version was skipped.

### Testing status

- **Done (software):** 25 `pytest` cases across `tests/test_camera_math.py`
  and `tests/test_world_model.py`, all currently passing. Every
  individual module (`serial_link.py`, `speed.py`, `warp.py`,
  `parking_maneuver.py`, `world.py`, `proximity.py`, and others) also
  carries a standalone `_run_tests()` self-test, independently runnable
  (e.g. `python3 -m control.parking_maneuver`) — spot-checked and
  passing. `main.py --dry-run --headless --frames 200` runs the complete
  pipeline end-to-end against synthetic frames with no exceptions.
- **Pending (physical):** the vision pipeline (HSV thresholds, contour
  aspect-ratio filter, distance/angle math) has only ever seen synthetic
  frames. Real-camera behaviour under real lighting, real pillar
  material/reflectivity, and real track geometry is untested. This is
  the single largest source of risk in the project and is called out
  as such rather than downplayed.

---

## Criterion 4 — Systems Thinking and Engineering Decisions

This section is deliberately about *why*, collecting the tradeoffs made
across the codebase into one place rather than leaving them scattered
across docstrings.

### Constraints that shaped the architecture

- **WRO §9.9–§9.11** (only a power switch and a start button are
  permitted interactions; no physical adjustments may enter data into
  the program): this is *why* `--challenge {OPEN,OBSTACLE}` is a CLI
  flag baked in before the round rather than a physical selector switch
  on the chassis — a physical switch read at runtime would risk being
  read as "entering data through physical adjustment" under §9.9, and a
  DQ for that reason on the first round would be a far worse outcome
  than accepting the operational cost of setting the flag before the
  robot is switched on.
- **WRO §11.10** (no active wireless during a round): this is why the
  Pi's onboard Wi-Fi must be disabled at the OS level rather than merely
  "not used" by the code — see `setup/disable_wifi.sh`, added this
  session specifically so this requirement has a runnable, repeatable
  artifact in the repo instead of being only a checklist line judges
  have to take on faith.

### Real tradeoffs, with what we gave up

1. **4-section lap tracking vs. the rulebook's 8-section count.**
   `planner.py` tracks laps as 4 straightforward-section crossings, not
   WRO's own 8-sections-per-lap (which includes corners, for scoring
   purposes). We accepted this because nothing in the current seat-memory
   or lap-completion logic needs corner-level resolution — but we
   documented explicitly that this is a load-bearing simplification: if
   corner-level scoring bookkeeping is ever added, `SECTIONS_PER_LAP`
   must change to 8 *in lockstep* with a `world_model/track.py` rewrite,
   not independently. Flagging that coupling now is cheaper than
   rediscovering it as a bug later.
2. **Left/right HC-SR04 plumbed but not wired into steering.** Covered
   in Criterion 2 — chose to expose the data (logged, on the HUD) without
   using it in the control loop, rather than either fully wiring it
   blind or not parsing it at all. This is a middle option chosen
   specifically to make the eventual on-track calibration step *smaller*
   (the hard parts — parsing, timing, telemetry — are already done)
   without taking on the risk of an unverified control-loop change.
3. **`LINE` uplink received but not actioned.** The IR line sensor's
   uplink event is parsed and logged as a cross-check signal, explicitly
   *not* wired as an authoritative navigation input. Camera-based
   corner-line detection (`camera/lines.py`) is the primary signal;
   letting a backup sensor silently override the primary one is a
   failure mode of its own (imagine the IR sensor false-triggering on a
   shadow and ending a lap early) — so the deliberate choice was
   "collect the data so it's available for debugging or a future
   fusion decision, but don't let it drive behaviour until that fusion
   is itself designed and tested."
4. **Parking-maneuver debounce (`PARK_STABLE_FRAMES`).** The parking
   controller requires both pixel-centering error *and* heading error to
   stay under threshold for several consecutive frames before declaring
   the maneuver complete, rather than stopping the instant the error
   crosses the threshold once. This trades a fraction of a second of
   extra maneuver time for avoiding a false "centered" declaration —
   because WRO §9.24.7 zeroes the parking score entirely if the vehicle
   touches a parking-lot limitation, overshooting to finish one frame
   early is a strictly worse trade than a slightly slower, confirmed
   stop.
5. **Mock-serial architecture instead of a separate test harness.**
   `control/serial_link.py` falls back to an in-memory mock backend
   whenever pyserial isn't installed, no Arduino is attached, or a write
   fails mid-run — and `main.py` uses the exact same code path either
   way. We chose this over writing a separate simulation harness
   specifically so that `--dry-run` testing exercises the *real*
   decision logic (planner transitions, speed scheduling, steering
   selection), not a parallel approximation of it that could silently
   drift out of sync with the real-hardware path.

### Risk / failure-mode awareness

- **Loss of Pi↔Arduino link mid-round:** the firmware's watchdog stops
  the drive motor if no downlink command arrives for >500 ms, rather
  than coasting on the last command indefinitely — chosen because a Pi
  crash or USB disconnect mid-round with the motor still driving the
  last commanded speed is a much worse failure (an uncontrolled vehicle)
  than a clean stop.
- **Unconfirmed sensor-mount orientation assumption:** `seat_estimator.py`
  explicitly flags that its near/far ↔ top/bottom seat-row mapping is
  *inferred* from Figure 3 and not yet confirmed against the physical
  camera mount, and documents exactly which constant to flip
  (`TOP_BOTTOM_SPLIT_CM`'s branch logic) if calibration shows it's
  mirrored — turning a "we'll find out on the day" risk into a
  "we know exactly what to check and how to fix it" risk.

---

## Criterion 5 — Reproducibility and GitHub Quality

### What's in the repository, and why it's organized this way

```
main.py                 Entry point — wires every stage together
firmware/                Arduino Uno sketch (sensors, motor/servo, watchdog)
camera/                  Capture, warp, HSV, contours, tracking, corridor, parking
world_model/             Section/seat memory, the 36-card catalog, lap tracking
planner/                 Top-level state machine
control/                 PID, speed scheduling, serial link, parking, collision guard
config/                  Tunable HSV ranges (persisted from hsv_tuner.py)
utils/                   FPS counter, CSV telemetry logger
tests/                   pytest suites (115 passing cases)
docs/                    Build guide + vision-pipeline walkthrough (HTML)
setup/                   One-shot hardware/OS setup scripts (e.g. Wi-Fi disable)
readme.md                Build/run/calibration instructions (~17,000 characters)
ENGINEERING_JOURNAL.md   This document
CHANGELOG.md             Dated, reasoned version history
```

Every module carries a docstring explaining *why* it exists and what it
deliberately does not do, not just a function-level comment — the intent
is that another team could read a single file and understand both its
role and its boundaries without cross-referencing five other files.

### Reproducibility checklist against WRO §7

| Requirement | Status |
|---|---|
| README ≥ 5,000 characters, English | ✅ `readme.md` is ~17,000 characters |
| Discussion of mobility/power/sense/obstacle management | ✅ `readme.md` "What it does"; this journal goes deeper on *why* |
| Photos (every side, top, bottom, team) | ❌ Pending — placeholder checklist exists at `media/README.md`, but the images themselves require the physical vehicle |
| ≥ 30 s autonomous-driving YouTube video, one per challenge | ❌ Pending — placeholder table with recording checklist at `media/VIDEO_LINKS.md`, still requires the physical vehicle |
| GitHub repo public, ≥ 3 commits | 🟡 **Local history now exists** — `git log` shows 9 commits grouped by subsystem (world-model, camera, control/planner, firmware, tests, docs, session docs). Push this to a real GitHub remote and make it public. |
| Commits timed 2 mo / 1 mo / 2 wk before competition | ❌ **Not satisfied, and can't be by any tool.** The commits above were all made in one sitting today, not spread across real calendar time — no tool operating on a static directory can retroactively fabricate an authentic, dated timeline. From here forward, real commits made as the hardware items in this journal get resolved (wiring, calibration, field tests) will build the genuine timeline WRO requires. Don't backdate commit timestamps to fake this — that's a rule-3.7/3.8-adjacent integrity problem, not a shortcut. |
| Code commented, buildable by another team | ✅ Every module documented; `readme.md` "Running it" gives exact commands |
| Repo stays public ≥ 12 months post-competition | ⏳ Operational commitment, not a code artifact — team must ensure this after submission |
| Hardcopy of documentation submitted at the international final (WRO §7) | ⏳ Print `readme.md` and this journal (or an exported PDF of both) and bring it physically to the final — GitHub scoring is primary, but the rule requires a physical copy be handed in as well. Not a code/repo artifact; a team logistics item for competition day. |

### Testing status

- **Done:** `python3 -m pytest tests/` → 115/115 passing, reproducible from
  a clean checkout with only `requirements.txt` installed.
  `python3 main.py --dry-run --headless --frames 200` runs clean with no
  hardware attached — this is the reproducibility bar another team
  (or a judge without your exact hardware) can actually clear themselves.
- **Pending:** physical reproducibility (another team building this exact
  BOM and getting the same on-track behaviour) is untested by definition
  until this team's own physical build exists as a reference point.

---

## Summary — what this journal is and isn't claiming

This is a **software-complete, hardware-pending** project. The rubric
levels most relevant right now are **4 (competent, structured,
reproducible engineering)** across all five criteria — every design
decision above is real, documented, and testable in software, and none
of it depends on measurements that don't exist yet. Reaching **6
(advanced, with tradeoff data from physical testing)** requires exactly
the items already tracked in `readme.md` → *Known limitations* and
`PUNCHLIST_STATUS.md`: on-robot calibration, physical dry runs, and
build-verification photos/video. We chose to document this honestly
rather than backfill placeholder numbers into this journal, because WRO's
own rubric explicitly penalizes overclaiming (see the General Rules'
"Tested over 20+ runs" note, which we removed from `docs/index.html`
this session for exactly this reason) — an unverified "6" is worth less
to a judge than a well-evidenced "4."
