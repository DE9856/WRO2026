import cv2

from camera.capture  import init_camera, read_frame, release_camera
from camera.hsv      import get_red_mask, get_green_mask
from camera.contours import detect_objects
from camera.morphology import clean_mask
from camera.angle    import estimate_angle, compute_error
from camera.tracker  import CentroidTracker
from camera.fps      import FPSCounter
from control.pid     import PIDController

# =====================================
# CAMERA SETUP
# =====================================

cap = init_camera()
fps_counter = FPSCounter()

# =====================================
# TRACKERS
# =====================================

red_tracker   = CentroidTracker()
green_tracker = CentroidTracker()

# =====================================
# PID CONTROLLER
# =====================================

pid = PIDController(
    kp=0.04,
    ki=0.0,
    kd=0.01
)

# =====================================
# MAIN LOOP
# =====================================

while True:

    frame = read_frame(cap)

    if frame is None:
        print("[ERROR] Failed to read frame")
        break

    fps_counter.tick()

    # =====================================
    # FRAME DIMENSIONS
    # =====================================

    frame_height, frame_width, _ = frame.shape

    # =====================================
    # ROI CROP
    # Requires frame >= 560 x 480.
    # At 640x480 (set in capture.py) this
    # gives a 480x300 region of interest.
    # =====================================

    roi = frame[180:480, 80:560]

    roi_height, roi_width, _ = roi.shape

    # Draw ROI rectangle on main frame
    cv2.rectangle(
        frame,
        (80, 180),
        (560, 480),
        (255, 0, 0),
        2
    )

    # =====================================
    # STEERING ZONES
    # =====================================

    left_zone  = roi_width // 3
    right_zone = 2 * roi_width // 3

    cv2.line(
        roi,
        (left_zone, 0),
        (left_zone, roi_height),
        (255, 255, 255),
        2
    )

    cv2.line(
        roi,
        (right_zone, 0),
        (right_zone, roi_height),
        (255, 255, 255),
        2
    )

    # =====================================
    # HSV CONVERSION
    # =====================================
    roi = cv2.GaussianBlur(roi, (5, 5), 0)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # =====================================
    # COLOR MASKS
    # =====================================

    red_mask   = get_red_mask(hsv)
    green_mask = get_green_mask(hsv)

    # =====================================
    # MORPHOLOGY CLEANUP
    # =====================================

    red_mask   = clean_mask(red_mask)
    green_mask = clean_mask(green_mask)

    # =====================================
    # OBJECT DETECTION
    # =====================================

    red_objects = detect_objects(
        red_mask,
        roi,
        "RED",
        (0, 0, 255)
    )

    green_objects = detect_objects(
        green_mask,
        roi,
        "GREEN",
        (0, 255, 0)
    )

    # =====================================
    # TEMPORAL TRACKING
    # =====================================

    closest_red   = red_tracker.track(red_objects)
    closest_green = green_tracker.track(green_objects)

    # =====================================
    # DEFAULT VALUES
    # =====================================

    steering_value = 0
    angle          = 0

    # =====================================
    # RED PILLAR BEHAVIOR
    # =====================================

    if closest_red:

        cx = closest_red["cx"]
        cy = closest_red["cy"]

        angle          = estimate_angle(cx)
        error          = compute_error(cx, "RED")
        steering_value = pid.compute(error)
        steering_value = max(-30, min(30, steering_value))

        cv2.circle(roi, (cx, cy), 8, (255, 255, 0), -1)

        cv2.putText(
            roi,
            f"{angle:.1f} deg",
            (cx, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2
        )

        cv2.putText(
            frame,
            "RED PILLAR",
            (50, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )

    # =====================================
    # GREEN PILLAR BEHAVIOR
    # =====================================

    elif closest_green:

        cx = closest_green["cx"]
        cy = closest_green["cy"]

        angle          = estimate_angle(cx)
        error          = compute_error(cx, "GREEN")
        steering_value = pid.compute(error)
        steering_value = max(-30, min(30, steering_value))

        cv2.circle(roi, (cx, cy), 8, (255, 255, 0), -1)

        cv2.putText(
            roi,
            f"{angle:.1f} deg",
            (cx, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2
        )

        cv2.putText(
            frame,
            "GREEN PILLAR",
            (50, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

    # =====================================
    # HUD — Steering + FPS
    # =====================================

    cv2.putText(
        frame,
        f"Steering: {steering_value:.2f}",
        (50, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 255),
        3
    )

    cv2.putText(
        frame,
        f"FPS: {fps_counter.get()}",
        (frame_width - 150, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (200, 200, 200),
        2
    )

    # =====================================
    # DISPLAY WINDOWS
    # =====================================

    cv2.imshow("Frame",      frame)
    cv2.imshow("ROI",        roi)
    cv2.imshow("Red Mask",   red_mask)
    cv2.imshow("Green Mask", green_mask)

    # =====================================
    # EXIT — press ESC
    # =====================================

    if cv2.waitKey(1) == 27:
        break

# =====================================
# CLEANUP
# =====================================

release_camera(cap)
cv2.destroyAllWindows()