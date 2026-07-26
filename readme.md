# WRO 2026 Future Engineers — Vision + Steering Prototype

An early-stage autonomous vehicle pipeline for the [WRO Future Engineers
2026](https://wro-association.org/) Self-Driving Cars challenge: a Raspberry
Pi + camera setup that detects the red/green traffic-sign pillars and
computes a PID steering correction to keep a fixed clearance on the correct
side of them (Game Rules 2026 §9.19 — red pillar on the right, green pillar
on the left).

> **Status: early prototype.** This repo currently implements the *vision +
> steering* half of the pipeline only. It detects pillars and computes a
> steering angle, and displays everything on screen — it does **not** yet
> send commands to a motor controller, drive on tracks with no pillars
> (Open Challenge), or use the `planner`/`world_model` scaffolding for
> anything beyond a standalone demo script. See [Known
> Limitations](#known-limitations--roadmap) below before assuming this
> drives a physical vehicle end-to-end.

## What it does today

- Captures frames from a Raspberry Pi camera (`picamera2`) and crops a
  fixed ROI (`camera/capture.py`, `main.py`).
- Converts the ROI to HSV and thresholds it for red and green
  (`camera/hsv.py`, `config/hsv_config.py`).
- Cleans the resulting masks with morphological open/close
  (`camera/morphology.py`).
- Finds pillar-shaped contours (tall, not wide — filters out floor
  reflections) and estimates their distance via similar triangles from
  known pillar width (`camera/contours.py`, `camera/distance.py`).
- Tracks the nearest pillar frame-to-frame by centroid proximity
  (`camera/tracker.py`).
- Computes a signed pixel error that targets a fixed clearance offset from
  whichever pillar is closest (red → pass on its right, green → pass on
  its left) and feeds it through a PID controller to get a steering value
  clamped to ±30° (`camera/angle.py`, `control/pid.py`).
- Draws a live HUD (steering value, FPS, pillar overlays) in several
  `cv2.imshow` windows for on-the-bench debugging.
- Ships an interactive HSV tuner (`hsv_tuner.py`) with trackbars for
  re-calibrating the red/green ranges under different lighting.

## Project layout

```
main.py                    Entry point — the camera→mask→detect→steer loop
camera/
  capture.py                Picamera2 setup (Raspberry Pi specific)
  hsv.py                     HSV thresholding for red/green
  morphology.py              Mask cleanup (open + close)
  contours.py                Contour → pillar detection + distance estimate
  distance.py                Similar-triangles distance formula
  angle.py                   Steering-angle / clearance-error math
  tracker.py                 Frame-to-frame centroid tracking
config/
  hsv_config.py               Hardcoded HSV ranges (red/green only)
control/
  pid.py                     PID controller
utils/
  fps.py                     Rolling FPS counter
world_model/
  obstacle.py                 Obstacle data class
  vehicle_state.py             Lap/section/speed/steering state container
  track.py                    Corridor-width holder (bare stub)
  memory.py                    Flat in-memory obstacle list
  world.py                    Wires the above together, print_state() debug dump
planner/
  planner.py                  Empty — scaffolded package, no logic yet
tests/
  test_world_model.py          Manual demo script (not an automated test suite)
hsv_tuner.py                  Standalone HSV calibration tool
```

## Requirements

- Raspberry Pi with a compatible camera module (tuned for the OV5647 /
  Pi Camera v1.3, ~54° horizontal FOV — see `camera/angle.py`)
- Python 3.9+
- `opencv-python`, `numpy`, `picamera2`

```bash
pip install opencv-python numpy
# picamera2 ships with Raspberry Pi OS (Bullseye+); if missing:
sudo apt install -y python3-picamera2
```

`camera/capture.py` imports `picamera2` directly, so this will **not** run
on a laptop with a regular USB webcam without modification.

## Running it

```bash
python3 main.py
```

- A blue rectangle shows the ROI crop on the full-frame window.
- White vertical lines mark the left/right steering zones inside the ROI.
- When a red or green pillar is tracked, its bounding box, centroid, and
  estimated distance/angle are overlaid, and the current steering value is
  shown top-left.
- Press **ESC** to quit; the camera and windows are released/closed on exit.

There is currently no CLI flag, no headless mode, and no hardware output —
this is a vision-and-math debugging tool, run it with a monitor attached.

## Calibrating colours

Lighting changes the red/green thresholds significantly. Re-tune with:

```bash
python3 hsv_tuner.py
```

Adjust the trackbars until only the pillars are white in the mask preview,
then press `r` / `g` to print the new ranges to the terminal and copy them
into `config/hsv_config.py`.

`camera/distance.py`'s `FOCAL_LENGTH = 620` is also a fixed constant — it
was calibrated against a specific camera/lens combination and should be
re-measured (`CALIBRATION_MODE = True` prints raw pixel widths to help)
if the camera or mount changes.

## Testing

`tests/test_world_model.py` is a manual smoke-test script, not an
automated `pytest`/`unittest` suite — it constructs two `Obstacle`s, adds
them to a `WorldModel`, and prints the result for visual inspection:

```bash
python3 -m tests.test_world_model
```

There is no automated coverage yet for the camera math modules
(`contours.py`, `angle.py`, `distance.py`, `tracker.py`).

## Known limitations / roadmap

This snapshot is the vision+steering half of the vehicle; the following
are known gaps rather than bugs, listed roughly in the order they'd block
a real competition run:

1. **No speed/motor output.** `main.py` computes `steering_value` but
   never computes or sends a throttle value, and there is no serial (or
   any other) link to a motor controller — the loop only drives
   `cv2.imshow`.
2. **No steering source for Open Challenge.** Steering is driven entirely
   by `closest_red`/`closest_green`; Open Challenge tracks have no
   pillars at all (WRO Game Rules 2026 §5/§8), so there is currently
   nothing to steer by on that track type.
3. **`world_model` isn't wired into `main.py`.** `WorldModel`,
   `VehicleState`, `Track`, and `MemoryManager` exist and are exercised
   by `tests/test_world_model.py`, but the main loop never constructs or
   updates them.
4. **`planner/planner.py` is empty.** No lap/section state machine,
   no parking logic, no challenge-round handling exists yet.
5. **Only red/green are detected.** No magenta (parking markers) or
   orange/blue (corner boundary lines) support in `config/hsv_config.py`
   or `camera/hsv.py`.
6. **No corridor/wall geometry.** Distance and steering are computed
   purely from the tracked pillar; there's no wall-following fallback
   and no perspective/bird's-eye correction.
7. **No telemetry/logging.** Nothing is written to disk — all feedback
   is the live `cv2.imshow` HUD, which disappears once the process exits.

## WRO reference

This project targets the **WRO 2026 Future Engineers — Self-Driving
Cars** category. See the official General Rules document (2026 season)
for the authoritative game description, scoring, and vehicle
regulations this codebase is built against.