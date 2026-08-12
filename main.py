"""
main.py
WRO 2026 Future Engineers — full pipeline entry point.

This file wires together every stage of the vehicle:
    camera -> colour masks -> detection -> world model / planner
    -> steering source selection -> speed scheduling -> serial output

REAL HARDWARE (default): run with no arguments on the robot. It opens
the Logitech C270 via camera/capture.py and the motor controller over
serial via control/serial_link.py.

DRY RUN (--dry-run): runs the exact same pipeline against synthetically
generated frames instead of a live camera, and forces the serial link
into mock mode, so the full wiring (steering source selection, speed
scheduling, planner state transitions, corner-boundary detection,
parking hand-off, telemetry logging) can be exercised and proven to run
end-to-end without any hardware attached -- e.g. in CI, or on a laptop
before the robot exists. It is NOT a stand-in for the real vision
pipeline: every module downstream of frame acquisition is 100% the same
code path that runs on the real robot; only the frame *source* and the
serial *backend* change.

    python3 main.py --dry-run --headless --frames 200
"""

import argparse

import cv2
import numpy as np

from camera.capture    import init_camera, read_frame, release_camera
from camera.hsv        import (
    get_red_mask, get_green_mask,
    get_magenta_mask, get_orange_mask, get_blue_mask, get_black_mask,
)
from camera.contours   import detect_objects
from camera.morphology import clean_mask
from camera.angle      import estimate_angle, compute_error
from camera.tracker    import CentroidTracker
from camera.parking    import locate_parking_lot
from camera.lines      import detect_corner_line
from camera.corridor   import estimate_corridor, corridor_error, ultrasonic_corridor_error
from camera.warp       import warp_frame, corridor_width_cm, WARP_OUT_WIDTH, WARP_OUT_HEIGHT
from utils.fps         import FPSCounter
from utils.telemetry   import TelemetryLogger
from control.pid       import PIDController
from control.speed     import SpeedController
from control.serial_link      import SerialLink
from control.parking_maneuver import ParkingManeuver
from control.proximity        import ParkingCollisionGuard

from world_model.obstacle         import RED, GREEN
from world_model.world            import WorldModel
from world_model.vehicle_state    import VehicleState
from world_model.section_observer import SectionObserver
from world_model.track            import Track
from planner.planner              import Planner, ChallengeType
from config.hsv_config            import get_ranges


def _mid_color_bgr(color_name: str) -> tuple:
    """
    Pick a BGR paint colour guaranteed to land inside the CURRENTLY
    ACTIVE hsv_config range for `color_name` (tuned config/hsv_ranges.json
    if present, else the module defaults) rather than a hardcoded BGR
    literal. Hardcoded literals silently fall outside a real tuned range
    (this exact bug bit the first version of SyntheticCamera below: a
    pixel with H=16 fell outside a tuned ORANGE upper-V of 236 even
    though it looked "orange" by eye) -- deriving the colour from
    whatever range is actually loaded keeps --dry-run correct on every
    machine regardless of whether hsv_tuner.py has been run there.
    """
    r = get_ranges(color_name)[0]
    lower, upper = r["lower"], r["upper"]
    mid_hsv = np.uint8([[[
        (lower[0] + upper[0]) // 2,
        (lower[1] + upper[1]) // 2,
        (lower[2] + upper[2]) // 2,
    ]]])
    bgr = cv2.cvtColor(mid_hsv, cv2.COLOR_HSV2BGR)[0, 0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


# =====================================
# CLI ARGUMENTS
# =====================================

def parse_args():
    p = argparse.ArgumentParser(description="WRO 2026 Future Engineers vehicle pipeline")
    p.add_argument("--dry-run", action="store_true",
                    help="Use synthetic frames instead of a live camera (no hardware needed).")
    p.add_argument("--frames", type=int, default=None,
                    help="Stop after this many frames (dry-run only; default: run until DONE).")
    p.add_argument("--headless", action="store_true",
                    help="Skip cv2.imshow windows / key handling (for CI or no-display hosts).")
    p.add_argument("--mock-serial", action="store_true",
                    help="Force the serial link into mock mode even on real hardware runs.")
    p.add_argument("--port", default="/dev/ttyACM0", help="Serial port for the motor controller.")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--challenge", choices=["OPEN", "OBSTACLE"], default="OBSTACLE")
    p.add_argument("--excluded-color", choices=["RED", "GREEN"], default="RED",
                    help="Obstacle Challenge coin-toss result (WRO Section8 step 2) -- ignored for OPEN.")
    p.add_argument("--no-telemetry", action="store_true", help="Disable CSV telemetry logging.")
    p.add_argument("--auto-start", action="store_true",
                    help="Skip WAIT and press the start button automatically (dry-run convenience).")
    p.add_argument("--park-start-strategy", choices=["creep", "hold"], default="creep",
                    help="What ParkingManeuver does the instant PARK_EXEC begins, before a lot "
                         "has ever been seen: 'creep' (default) eases forward straight so the "
                         "camera can find the magenta markers; 'hold' stays fully stopped until "
                         "a lot is visible. See control/parking_maneuver.py's START_STRATEGIES.")
    return p.parse_args()


# =====================================
# SYNTHETIC FRAME SOURCE (--dry-run only)
# Draws a plausible ROI-sized scene: black exterior walls always
# present (drives camera/corridor.py), plus a red pillar that drifts
# across frames in the middle third of the run, plus a periodic orange
# corner-line flash so planner.section_boundary_crossed() actually
# fires and gets exercised end-to-end.
# =====================================

class SyntheticCamera:
    # Frame number after which magenta parking markers appear -- comfortably
    # past 3 laps worth of corner crossings (4 sections/lap * 150 frames per
    # crossing cycle * 3 laps = 1800) so a long enough --frames run actually
    # exercises PARK_SEEK -> PARK_EXEC -> DONE end-to-end, not just OBS_DRIVE.
    PARKING_MARKERS_APPEAR_AT_FRAME = 1850

    def __init__(self, width=640, height=480, challenge: str = "OBSTACLE"):
        self.width = width
        self.height = height
        self.challenge = challenge  # "OPEN" tracks have NO traffic signs at all (WRO Section5/Section8)
        self._frame_no = 0
        # Resolved once from the active hsv_config (tuned or default) —
        # see _mid_color_bgr() docstring for why this must not be a
        # hardcoded BGR literal.
        self._black_bgr = (10, 10, 10)   # BLACK isn't picked by hue, a near-zero-V literal is safe
        self._red_bgr = _mid_color_bgr("RED")
        self._orange_bgr = _mid_color_bgr("ORANGE")
        self._magenta_bgr = _mid_color_bgr("MAGENTA")

    def read(self):
        self._frame_no += 1
        frame = np.full((self.height, self.width, 3), 200, dtype=np.uint8)  # light grey floor

        # Exterior + interior walls -> near-black bands. Widths are
        # chosen so the bands actually fall inside the ROI crop
        # (frame[180:480, 80:560]) -- a wall drawn only at the extreme
        # frame edges (e.g. x<40) would sit entirely outside the ROI and
        # never reach camera/corridor.py at all.
        cv2.rectangle(frame, (0, 0), (140, self.height), self._black_bgr, -1)               # left wall
        cv2.rectangle(frame, (self.width - 140, 0), (self.width, self.height), self._black_bgr, -1)  # right wall

        # A red pillar drifting left->right through the middle third of the
        # run -- Obstacle Challenge only. Real Open Challenge tracks have
        # NO traffic signs at all (WRO Game Rules 2026 Section5/Section8), so a
        # dry-run --challenge OPEN should never see one either, matching
        # what forces corridor centering to be the ONLY steering source.
        cycle = self._frame_no % 150
        if self.challenge == "OBSTACLE" and 30 <= cycle < 110:
            px = 200 + int((cycle - 30) * 2.5)
            cv2.rectangle(frame, (px, 250), (px + 25, 340), self._red_bgr, -1)

        # Periodic orange corner-line flash every 150 frames -> exercises
        # planner.section_boundary_crossed() the same way a real corner
        # would. Positioned well inside the ROI's x-range (80-560 in
        # full-frame coords) with margin on both sides, and wide enough
        # (70px) to survive the GaussianBlur + MORPH_OPEN pipeline stage
        # (camera/morphology.py) rather than being eroded away as noise.
        if cycle < 8:
            cv2.rectangle(frame, (470, 200), (540, 400), self._orange_bgr, -1)

        # Two magenta parking markers, straddling the ROI's horizontal
        # center so ParkingManeuver converges to "centered" without the
        # (nonexistent, in this synthetic scene) vehicle needing to
        # actually move -- proves the PARK_SEEK -> PARK_EXEC -> DONE
        # wiring end-to-end (Gap #5) once enough frames have elapsed.
        if self._frame_no >= self.PARKING_MARKERS_APPEAR_AT_FRAME:
            cv2.rectangle(frame, (270, 300), (300, 340), self._magenta_bgr, -1)  # left marker
            cv2.rectangle(frame, (340, 300), (370, 340), self._magenta_bgr, -1)  # right marker

        return True, frame

    def release(self):
        pass


def init_synthetic_camera(challenge: str = "OBSTACLE"):
    return SyntheticCamera(challenge=challenge)


# =====================================
# ENTRY POINT
# =====================================

def main():
    args = parse_args()

    CHALLENGE = ChallengeType.OPEN if args.challenge == "OPEN" else ChallengeType.OBSTACLE
    EXCLUDED_COLOR = RED if args.excluded_color == "RED" else GREEN

    # =====================================
    # CAMERA SETUP
    # =====================================
    if args.dry_run:
        cap = init_synthetic_camera(challenge=args.challenge)
        print("[main] --dry-run: using SyntheticCamera (no hardware required).")
    else:
        cap = init_camera()

    fps_counter = FPSCounter()

    # =====================================
    # TRACKERS
    # =====================================
    red_tracker = CentroidTracker()
    green_tracker = CentroidTracker()

    # =====================================
    # PID CONTROLLER (shared by pillar-offset steering AND corridor
    # centering -- Gap #1 fix -- since both produce the same kind of
    # signed pixel error and want the same damping behaviour)
    # =====================================
    pid = PIDController(kp=0.04, ki=0.0, kd=0.01)

    # =====================================
    # SPEED SCHEDULER (Gap #2 fix)
    # =====================================
    speed_controller = SpeedController()

    # =====================================
    # SERIAL OUTPUT LINK (Gap #3 fix)
    # =====================================
    serial_link = SerialLink(
        port=args.port, baud=args.baud,
        force_mock=(args.mock_serial or args.dry_run),
        verbose_mock=not args.headless,
    )

    # =====================================
    # PARKING MANEUVER CONTROLLER (Gap #5 fix)
    # =====================================
    parking_maneuver = ParkingManeuver(start_strategy=args.park_start_strategy)

    # =====================================
    # PARKING-MARKER PROXIMITY/COLLISION GUARD (C.14 fix)
    # =====================================
    collision_guard = ParkingCollisionGuard()

    # =====================================
    # CORRIDOR-WIDTH MEMORY (Gap #7 fix)
    # =====================================
    track = Track()

    # =====================================
    # TELEMETRY (Gap #8 fix)
    # =====================================
    telemetry = TelemetryLogger(enabled=not args.no_telemetry)

    # =====================================
    # WORLD MODEL + PLANNER WIRING
    # EXCLUDED_COLOR, CHALLENGE, and DIRECTION all come from the
    # pre-round coin toss / judge setup (Game Rules 2026 Section5, Section8, Section9.3) --
    # none of this is camera-detectable, so it's passed in via CLI args
    # (--challenge / --excluded-color) rather than hand-edited constants.
    # =====================================
    world_model = WorldModel(excluded_color=EXCLUDED_COLOR)
    vehicle_state = VehicleState()
    section_observer = SectionObserver()
    planner = Planner(
        challenge=CHALLENGE,
        vehicle_state=vehicle_state,
        world_model=world_model,
        section_observer=section_observer,
    )

    if args.auto_start:
        planner.start_button_pressed()

    # Corner-exit rising-edge tracker (see planner.section_boundary_crossed()
    # docstring for what this feeds).
    was_exiting_corner = False

    # Steering-value memory: Gap #1's corridor fallback can occasionally
    # find no wall on a given frame (both walls out of view mid-turn).
    # Holding the last commanded value instead of snapping to 0 avoids a
    # single dropped frame jerking the wheel straight.
    last_steering_value = 0.0

    # Most recent HC-SR04 readings (control/proximity.py's
    # ParkingCollisionGuard's cue 1 uses the forward one), updated from
    # the Arduino uplink events processed later in this same loop. None
    # until the first "DIST_F=<cm>"/"DIST_L=<cm>"/"DIST_R=<cm>" line
    # arrives -- always the case in --dry-run/mock-serial, where the
    # guard gracefully falls back to its camera-only cue. Left/right also
    # feed camera/corridor.py::ultrasonic_corridor_error() as a
    # last-resort steering fallback (see the STEERING SOURCE SELECTION
    # block below) when vision finds no wall pixels at all -- that
    # conversion is a PLACEHOLDER, not yet calibrated against the real
    # track (see firmware's "NOTE ON HC-SR04 USAGE").
    forward_distance_cm = None
    left_distance_cm = None
    right_distance_cm = None

    # Most recent MPU-6050 yaw heading (degrees, drifting integrator --
    # see vehicle_controller.ino's serviceImu()). None if no MPU-6050 is
    # wired/detected (setupImu() sends no IMU= lines in that case) or in
    # --dry-run/mock-serial. control/parking_maneuver.py uses the DELTA
    # from whatever this was when PARK_EXEC started, not the absolute
    # value, so a nonzero boot heading doesn't matter.
    imu_heading_deg = None
    park_exec_reference_heading_deg = None

    frame_count = 0

    # =====================================
    # MAIN LOOP
    # =====================================
    try:
        while True:

            if args.dry_run:
                ok, frame = cap.read()
            else:
                frame = read_frame(cap)
                ok = frame is not None

            if not ok or frame is None:
                print("[ERROR] Failed to read frame")
                break

            frame_count += 1
            fps_counter.tick()

            # =====================================
            # FRAME DIMENSIONS
            # =====================================
            frame_height, frame_width, _ = frame.shape

            # =====================================
            # ROI CROP
            # Requires frame >= 560 x 480.
            # At 640x480 (set in capture.py) this gives a 480x300 ROI.
            # =====================================
            roi = frame[180:480, 80:560]
            roi_height, roi_width, _ = roi.shape

            if not args.headless:
                cv2.rectangle(frame, (80, 180), (560, 480), (255, 0, 0), 2)

            # =====================================
            # STEERING ZONES (HUD only)
            # =====================================
            left_zone = roi_width // 3
            right_zone = 2 * roi_width // 3
            if not args.headless:
                cv2.line(roi, (left_zone, 0), (left_zone, roi_height), (255, 255, 255), 2)
                cv2.line(roi, (right_zone, 0), (right_zone, roi_height), (255, 255, 255), 2)

            # =====================================
            # HSV CONVERSION
            # =====================================
            roi_blurred = cv2.GaussianBlur(roi, (5, 5), 0)
            hsv = cv2.cvtColor(roi_blurred, cv2.COLOR_BGR2HSV)

            # =====================================
            # COLOR MASKS -- all six tracked colours (Gap #1 adds BLACK)
            # =====================================
            red_mask     = clean_mask(get_red_mask(hsv))
            green_mask   = clean_mask(get_green_mask(hsv))
            magenta_mask = clean_mask(get_magenta_mask(hsv))
            orange_mask  = clean_mask(get_orange_mask(hsv))
            blue_mask    = clean_mask(get_blue_mask(hsv))
            black_mask   = clean_mask(get_black_mask(hsv))

            # =====================================
            # PILLAR DETECTION (red / green)
            # =====================================
            red_objects = detect_objects(red_mask, roi, "RED", (0, 0, 255))
            green_objects = detect_objects(green_mask, roi, "GREEN", (0, 255, 0))

            # =====================================
            # WORLD MODEL -- SEAT ACCUMULATION
            # =====================================
            section_observer.update(
                red_detections=red_objects, green_detections=green_objects, roi_width=roi_width
            )

            # =====================================
            # TEMPORAL TRACKING
            # =====================================
            closest_red = red_tracker.track(red_objects)
            closest_green = green_tracker.track(green_objects)

            # =====================================
            # CORRIDOR ESTIMATION (Gap #1 / #4 / #7)
            # Computed every frame (not just when no pillar is visible)
            # so world_model/track.py's rolling width estimate stays
            # current for telemetry/journal evidence even while pillar
            # steering is in charge.
            # =====================================
            warped_wall_mask = warp_frame(black_mask, out_size=(WARP_OUT_WIDTH, WARP_OUT_HEIGHT))
            corridor = estimate_corridor(warped_wall_mask, WARP_OUT_WIDTH, WARP_OUT_HEIGHT)
            track.set_width(
                corridor["corridor_width_px"],
                width_cm=corridor_width_cm(corridor["corridor_width_px"]),
                section=vehicle_state.current_section,
            )

            # =====================================
            # STEERING SOURCE SELECTION
            # RED/GREEN pillar (Obstacle Challenge) takes priority when
            # visible; otherwise fall back to corridor centering -- this
            # is the Gap #1 fix: Open Challenge has NO pillars at all
            # (WRO Section5/Section8), so corridor centering is its ONLY steering
            # source, not a rare edge case.
            # =====================================
            steering_source = "NONE"
            pillar_color = ""
            pillar_cx = ""
            pillar_distance_cm = ""
            angle = 0.0
            confidence = 0.0
            steering_value = last_steering_value

            if closest_red:
                cx, cy = closest_red["cx"], closest_red["cy"]
                angle = estimate_angle(cx)
                error = compute_error(cx, "RED")
                steering_value = max(-30, min(30, pid.compute(error)))
                steering_source = "RED"
                pillar_color, pillar_cx = "RED", cx
                pillar_distance_cm = closest_red.get("distance", "")
                confidence = 1.0
                if not args.headless:
                    cv2.circle(roi, (cx, cy), 8, (255, 255, 0), -1)
                    cv2.putText(frame, "RED PILLAR", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            elif closest_green:
                cx, cy = closest_green["cx"], closest_green["cy"]
                angle = estimate_angle(cx)
                error = compute_error(cx, "GREEN")
                steering_value = max(-30, min(30, pid.compute(error)))
                steering_source = "GREEN"
                pillar_color, pillar_cx = "GREEN", cx
                pillar_distance_cm = closest_green.get("distance", "")
                confidence = 1.0
                if not args.headless:
                    cv2.circle(roi, (cx, cy), 8, (255, 255, 0), -1)
                    cv2.putText(frame, "GREEN PILLAR", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            else:
                err = corridor_error(corridor, WARP_OUT_WIDTH)
                if err is not None:
                    steering_value = max(-30, min(30, pid.compute(err)))
                    angle = steering_value  # corridor error has no independent angle estimate
                    steering_source = "CORRIDOR"
                    confidence = corridor["confidence"]
                else:
                    # Vision found no wall pixels at all this frame --
                    # last-resort fallback to the side HC-SR04 sensors
                    # before giving up and holding steering. PLACEHOLDER
                    # cm->px conversion, not yet track-calibrated (see
                    # camera/corridor.py's ultrasonic_corridor_error()
                    # docstring) -- capped confidence keeps it from ever
                    # being trusted as much as a real vision reading.
                    ultrasonic_fallback = ultrasonic_corridor_error(
                        left_distance_cm, right_distance_cm
                    )
                    if ultrasonic_fallback is not None:
                        us_err, us_confidence = ultrasonic_fallback
                        steering_value = max(-30, min(30, pid.compute(us_err)))
                        angle = steering_value
                        steering_source = "ULTRASONIC"
                        confidence = us_confidence
                    else:
                        # No pillar, no corridor reading, and no usable
                        # side ultrasonic reading either -- hold the
                        # last commanded steering rather than snapping
                        # straight (see last_steering_value comment above).
                        steering_source = "HOLD"
                        confidence = 0.0

            last_steering_value = steering_value

            # =====================================
            # MAGENTA PARKING MARKERS
            # =====================================
            parking_lot = locate_parking_lot(magenta_mask)

            if parking_lot and not args.headless:
                for marker, tag in ((parking_lot["left"], "L"), (parking_lot["right"], "R")):
                    mx, my, mw, mh = marker["x"], marker["y"], marker["w"], marker["h"]
                    cv2.rectangle(roi, (mx, my), (mx + mw, my + mh), (255, 0, 255), 2)
                    cv2.putText(roi, tag, (mx, my - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                cv2.circle(roi, (parking_lot["center_x"], roi_height // 2), 6, (255, 0, 255), -1)
                cv2.putText(
                    frame,
                    f"PARKING LOT center_x={parking_lot['center_x']} w={parking_lot['width_px']}px",
                    (50, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2,
                )

            # =====================================
            # ORANGE / BLUE CORNER LINES
            # =====================================
            corner = detect_corner_line(orange_mask, blue_mask, roi_width)

            if corner["color"] and not args.headless:
                blob = corner["blob"]
                draw_color = (0, 140, 255) if corner["color"] == "ORANGE" else (255, 140, 0)
                cv2.rectangle(roi, (blob["x"], blob["y"]), (blob["x"] + blob["w"], blob["y"] + blob["h"]), draw_color, 2)
                cv2.putText(
                    frame,
                    f"{corner['color']} LINE -> corner {corner['phase']} ({corner['side']} of frame)",
                    (50, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, draw_color, 2,
                )

            # =====================================
            # PLANNER -- SECTION BOUNDARY EVENT
            # =====================================
            is_exiting_corner = bool(corner["color"] and corner["phase"] == "EXITING")

            if is_exiting_corner and not was_exiting_corner and planner.is_driving():
                section_key_before = f"section_{vehicle_state.current_section}"
                seat_vector = section_observer.finalize(min_votes=2)
                seat_confidence = section_observer.confidence()

                planner.section_boundary_crossed(seat_vector=seat_vector, confidence=seat_confidence)

                matched_card = world_model.world_state.get(section_key_before)
                print(
                    f"[PLANNER] left {section_key_before} seats={seat_vector} "
                    f"-> {matched_card or 'NO MATCH'} | {planner}"
                )

            was_exiting_corner = is_exiting_corner

            # =====================================
            # PLANNER -- PARKING EVENTS + MANEUVER EXECUTION (Gap #5 fix)
            # =====================================
            is_parking_phase = planner.should_seek_parking() or planner.should_execute_parking()

            if is_parking_phase:
                planner.parking_lot_visible(parking_lot)

            if planner.should_execute_parking():
                # Capture the heading we had the instant PARK_EXEC began,
                # so ParkingManeuver can correct against the DELTA from
                # it (i.e. "are we still parallel to how we started")
                # rather than needing an absolute heading reference,
                # which the drifting gyro integrator can't provide over
                # a multi-minute session anyway (see vehicle_controller.
                # ino's serviceImu() docstring).
                if park_exec_reference_heading_deg is None and imu_heading_deg is not None:
                    park_exec_reference_heading_deg = imu_heading_deg

                heading_error_deg = None
                if imu_heading_deg is not None and park_exec_reference_heading_deg is not None:
                    heading_error_deg = imu_heading_deg - park_exec_reference_heading_deg
                    # wrap to (-180, 180]
                    while heading_error_deg > 180.0:
                        heading_error_deg -= 360.0
                    while heading_error_deg <= -180.0:
                        heading_error_deg += 360.0

                park_steer, park_speed, centered = parking_maneuver.update(
                    parking_lot, roi_width, heading_error_deg=heading_error_deg
                )
                steering_value = park_steer
                last_steering_value = park_steer
                speed_pwm = park_speed
                steering_source = "PARKING"

                # C.14 fix: proximity/collision awareness -- forward HC-SR04
                # range + marker apparent width, see control/proximity.py.
                # Checked BEFORE the "centered" branch below: touching a
                # marker forfeits parking points (WRO Section9.24.7) regardless
                # of how close to centered the manoeuvre otherwise was, so
                # it force-stops here rather than letting this frame's
                # ParkingManeuver speed command (computed above from pure
                # centering error, with no proximity awareness of its own)
                # carry the vehicle further into the marker.
                if collision_guard.update(forward_distance_cm, parking_lot, roi_width):
                    speed_pwm = 0.0
                    steering_source = "PARKING-TOUCH-STOP"
                    planner.parking_marker_touched()
                    print(
                        f"[main] Parking marker contact detected "
                        f"(forward_distance_cm={forward_distance_cm}) -> "
                        f"force-stop (WRO Section9.24.7). {planner}"
                    )
                elif centered:
                    planner.parking_complete()
            else:
                parking_maneuver.reset()
                collision_guard.reset()
                park_exec_reference_heading_deg = None
                # =====================================
                # SPEED SCHEDULING (Gap #2 fix)
                # =====================================
                speed_pwm = speed_controller.compute(
                    steering_angle_deg=angle,
                    confidence=confidence,
                    lap_phase=planner.lap_phase(),
                    parking=is_parking_phase,
                )

            if not planner.is_driving() and not is_parking_phase:
                speed_pwm = 0.0  # WAIT / DONE -- never command motion

            # =====================================
            # VEHICLE STATE -- write back what we actually commanded
            # (previously VehicleState.speed/steering_angle were dead
            # fields nothing ever wrote to)
            # =====================================
            vehicle_state.speed = speed_pwm
            vehicle_state.steering_angle = steering_value

            # =====================================
            # SERIAL OUTPUT (Gap #3 fix)
            # =====================================
            if planner.is_waiting():
                state_flag = "S"
            elif is_parking_phase:
                state_flag = "P"
            elif planner.is_done():
                state_flag = "S"
            else:
                state_flag = "D"

            serial_link.send(steering_value, speed_pwm, state_flag)

            # =====================================
            # TELEMETRY (Gap #8 fix)
            # =====================================
            telemetry.log(
                fps=fps_counter.get(),
                planner_state=str(planner.state.name),
                challenge=planner.challenge.value,
                lap=vehicle_state.current_lap,
                section=vehicle_state.current_section,
                lap_phase=planner.lap_phase(),
                steering_source=steering_source,
                steering_deg=round(steering_value, 2),
                speed_pwm=round(speed_pwm, 1),
                corridor_center_x=round(corridor["center_x"], 1) if corridor["center_x"] is not None else "",
                corridor_width_px=round(corridor["corridor_width_px"], 1) if corridor["corridor_width_px"] is not None else "",
                corridor_confidence=round(corridor["confidence"], 2),
                pillar_color=pillar_color,
                pillar_cx=pillar_cx,
                pillar_distance_cm=pillar_distance_cm,
                world_state_summary=str(world_model.world_state),
                dist_front_cm=forward_distance_cm if forward_distance_cm is not None else "",
                dist_left_cm=left_distance_cm if left_distance_cm is not None else "",
                dist_right_cm=right_distance_cm if right_distance_cm is not None else "",
                imu_heading_deg=round(imu_heading_deg, 2) if imu_heading_deg is not None else "",
            )

            # =====================================
            # HUD -- Steering + FPS + planner/world state
            # =====================================
            if not args.headless:
                cv2.putText(frame, f"Steering: {steering_value:.2f} ({steering_source})",
                            (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
                cv2.putText(frame, f"Speed: {speed_pwm:.1f}",
                            (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.putText(frame, f"FPS: {fps_counter.get()}",
                            (frame_width - 150, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
                cv2.putText(frame, f"Planner: {planner}",
                            (50, frame_height - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            (0, 255, 255) if planner.is_driving() else (200, 200, 200), 1)
                cv2.putText(frame, f"{track}",
                            (50, frame_height - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                cv2.putText(frame, f"World: {world_model.world_state}",
                            (50, frame_height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                us_text = (f"US F/L/R: "
                           f"{forward_distance_cm if forward_distance_cm is not None else '--'}/"
                           f"{left_distance_cm if left_distance_cm is not None else '--'}/"
                           f"{right_distance_cm if right_distance_cm is not None else '--'} cm  "
                           f"IMU: {imu_heading_deg if imu_heading_deg is not None else '--'} deg")
                cv2.putText(frame, us_text,
                            (frame_width - 320, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 255, 180), 1)

                cv2.imshow("Frame", frame)
                cv2.imshow("ROI", roi)
                cv2.imshow("Red Mask", red_mask)
                cv2.imshow("Green Mask", green_mask)
                cv2.imshow("Magenta Mask", magenta_mask)
                cv2.imshow("Orange Mask", orange_mask)
                cv2.imshow("Blue Mask", blue_mask)
                cv2.imshow("Black Mask (corridor)", black_mask)

            # =====================================
            # ARDUINO UPLINK EVENTS -- physical start button, backup line
            # sensor, and HC-SR04 forward range. Real hardware only
            # (control/serial_link.py::read_events() is a no-op in
            # mock/dry-run mode). See vehicle_controller.ino's
            # serviceStartButton() / serviceLineSensor() / serviceUltrasonic()
            # for the sender side.
            #
            # NOTE: MODE=OPEN / MODE=OBSTACLE is still handled here if it
            # ever arrives, but firmware/vehicle_controller.ino deliberately
            # does NOT send it -- the BOM only has two physical switches
            # (power + start), and WRO 9.9/9.10/9.11 make a third
            # mode-select switch risky. Set --challenge on the CLI instead.
            # This branch is dead code on the current firmware; left in so
            # a future firmware revision could add it without touching
            # main.py again.
            # =====================================
            for event in serial_link.read_events():
                if event == "BTN":
                    planner.start_button_pressed()
                    print("[main] Physical start button pressed -> round started.")
                elif event.startswith("MODE=") and planner.is_waiting():
                    requested = event.split("=", 1)[1].strip()
                    if requested in ("OPEN", "OBSTACLE"):
                        new_challenge = (
                            ChallengeType.OPEN if requested == "OPEN" else ChallengeType.OBSTACLE
                        )
                        if planner.challenge is not new_challenge:
                            planner.challenge = new_challenge
                            print(f"[main] Mode switch -> {requested} "
                                  f"(locked in once the start button is pressed).")
                elif event == "LINE":
                    # Backup lap-line signal. Not a substitute for the
                    # camera-based corner/section detection that drives
                    # planner.section_boundary_crossed() (main.py's
                    # ORANGE/BLUE corner-line block above) -- it's a
                    # sanity cross-check the team can look at in the
                    # telemetry log if the camera-based lap count ever
                    # looks wrong on a real run. Deliberately NOT wired
                    # into planner's lap/section state machine: doing so
                    # would let a single stray IR bounce silently
                    # override the primary, tested vision-based lap
                    # count, and validating "is this cross-check reliable
                    # enough to trust" needs real on-track testing this
                    # project can't do from a laptop. Logged instead.
                    print("[main] Backup IR line sensor triggered (cross-check only, "
                          "not wired into lap counting -- see main.py comment).")
                elif event.startswith("DIST_F=") or event.startswith("DIST="):
                    # Front HC-SR04 range (DIST_F= on current firmware;
                    # DIST= accepted too for compatibility with an older
                    # single-sensor firmware build). Feeds
                    # control/proximity.py's ParkingCollisionGuard next
                    # frame -- see the "PARKING EVENTS + MANEUVER
                    # EXECUTION" block above. A malformed/garbage line is
                    # ignored outright rather than crashing the vision
                    # loop over one bad reading.
                    try:
                        forward_distance_cm = float(event.split("=", 1)[1])
                    except ValueError:
                        pass
                elif event.startswith("DIST_L="):
                    try:
                        left_distance_cm = float(event.split("=", 1)[1])
                    except ValueError:
                        pass
                elif event.startswith("DIST_R="):
                    try:
                        right_distance_cm = float(event.split("=", 1)[1])
                    except ValueError:
                        pass
                elif event.startswith("IMU="):
                    # MPU-6050 integrated yaw heading (degrees). See
                    # vehicle_controller.ino's serviceImu() and
                    # control/parking_maneuver.py's heading-correction
                    # docstring for how this is used during PARK_EXEC.
                    try:
                        imu_heading_deg = float(event.split("=", 1)[1])
                    except ValueError:
                        pass

            # =====================================
            # START BUTTON (WRO Section9.11) -- SPACE stands in for the physical
            # button when a display is attached (e.g. --dry-run); on real
            # hardware the physical Arduino button above is what actually
            # starts the round.
            # =====================================
            if not args.headless:
                key = cv2.waitKey(1)
                if key == ord(" "):
                    planner.start_button_pressed()
                if key == 27:
                    break
            elif args.dry_run and frame_count == 1 and not args.auto_start:
                # Headless dry-run has no keyboard -- auto-press start
                # after the very first frame unless the caller already
                # did via --auto-start, so the loop actually exercises
                # DRIVE states instead of sitting in WAIT forever.
                planner.start_button_pressed()

            # =====================================
            # EXIT CONDITIONS
            # =====================================
            if planner.is_done():
                break
            if args.frames is not None and frame_count >= args.frames:
                break

    finally:
        # =====================================
        # CLEANUP -- always runs, even on exception/Ctrl-C
        # =====================================
        serial_link.send(0.0, 0.0, "S")  # final all-stop command
        serial_link.close()
        telemetry.close()
        if args.dry_run:
            cap.release()
        else:
            release_camera(cap)
        if not args.headless:
            cv2.destroyAllWindows()
        print(f"[main] Finished after {frame_count} frames. Final state: {planner}")


if __name__ == "__main__":
    main()
