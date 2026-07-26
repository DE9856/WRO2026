# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project does not yet follow Semantic Versioning strictly (pre-1.0,
hardware-in-the-loop prototype) — version numbers below are milestones,
not guarantees of API stability.

## [Unreleased]

Nothing yet — this section is the landing spot for the next round of
changes (see README → *Known limitations / roadmap* for the likely
next items: motor/serial output, Open Challenge corridor steering,
planner state machine, world-model integration).

## [0.1.0] — Initial vision + steering prototype

### Added
- Raspberry Pi camera capture pipeline via `picamera2`
  (`camera/capture.py`), fixed ROI crop for a 640×480 source.
- HSV-based colour thresholding for red and green pillars
  (`camera/hsv.py`, `config/hsv_config.py`).
- Morphological mask cleanup — open then close — to suppress noise
  before contour detection (`camera/morphology.py`).
- Contour-based pillar detection with an aspect-ratio filter (tall,
  not wide) to reject floor reflections, plus per-detection distance
  estimate via the similar-triangles formula (`camera/contours.py`,
  `camera/distance.py`).
- Frame-to-frame centroid tracking so steering follows one consistent
  pillar rather than jumping between detections (`camera/tracker.py`).
- Steering-angle and clearance-offset error calculation, tuned for the
  OV5647 camera's ~54° horizontal FOV (`camera/angle.py`).
- PID controller with proper `dt`-based integral and derivative terms
  and a persistent last-tick timestamp (`control/pid.py`).
- Live HUD overlay: steering value, FPS counter, pillar bounding
  boxes/centroids/distance, and per-mask debug windows.
- Interactive HSV tuner script with trackbars for on-site
  recalibration (`hsv_tuner.py`).
- Scaffolding for a future world model — `Obstacle`, `VehicleState`,
  `Track`, `MemoryManager`, `WorldModel` — exercised today only by a
  standalone manual demo script (`tests/test_world_model.py`), not yet
  connected to `main.py`.
- Empty `planner/` package reserved for the upcoming lap/section/
  challenge state machine.

### Known limitations (see README for full list)
- No throttle/speed output and no serial/motor-controller link —
  `main.py` computes steering only.
- No steering source when no pillar is visible (blocks Open Challenge,
  which has no pillars at all).
- `world_model` package is not wired into the main loop.
- `planner/planner.py` contains no logic yet.
- Only red/green are detected; no parking-marker or corner-line colours.
- No automated test coverage for the camera math modules.