import cv2

from camera.hsv import get_red_mask, get_green_mask
from camera.contours import detect_objects
from camera.morphology import clean_mask
from camera.angle import estimate_angle, compute_error
from camera.tracker import CentroidTracker
from control.pid import PIDController

# =====================================
# CAMERA SETUP
# =====================================

cap = cv2.VideoCapture(0)

# =====================================
# TRACKERS
# =====================================

red_tracker = CentroidTracker()
green_tracker = CentroidTracker()

# =====================================
# PID CONTROLLER
# =====================================

pid = PIDController(
    kp=1.2,
    ki=0.0,
    kd=0.4
)

# =====================================
# MAIN LOOP
# =====================================

while True:

    ret, frame = cap.read()

    if not ret:
        break

    # =====================================
    # FRAME DIMENSIONS
    # =====================================

    frame_height, frame_width, _ = frame.shape

    # =====================================
    # ROI CROP
    # =====================================

    roi = frame[180:480, 80:560]

    roi_height, roi_width, _ = roi.shape

    # Draw ROI rectangle
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

    left_zone = roi_width // 3
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

    hsv = cv2.cvtColor(
        roi,
        cv2.COLOR_BGR2HSV
    )

    # =====================================
    # COLOR MASKS
    # =====================================

    red_mask = get_red_mask(hsv)
    green_mask = get_green_mask(hsv)

    # =====================================
    # MORPHOLOGY CLEANUP
    # =====================================

    red_mask = clean_mask(red_mask)
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

    closest_red = red_tracker.track(red_objects)
    closest_green = green_tracker.track(green_objects)

    # =====================================
    # DEFAULT VALUES
    # =====================================

    steering_value = 0
    angle = 0

    # =====================================
    # RED PILLAR BEHAVIOR
    # =====================================

    if closest_red:

        cx = closest_red["cx"]
        cy = closest_red["cy"]

        angle = estimate_angle(cx)
        error = compute_error(cx, "RED")

        # =====================================
        # PID CONTROL
        # =====================================

        steering_value = pid.compute(error)

        # Clamp steering
        steering_value = max(-30, min(30, steering_value))

        # =====================================
        # VISUALIZATION
        # =====================================

        # Tracking point
        cv2.circle(
            roi,
            (cx, cy),
            8,
            (255, 255, 0),
            -1
        )

        # Angle display
        cv2.putText(
            roi,
            f"{angle:.1f} deg",
            (cx, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2
        )

        # Object label
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

        angle = estimate_angle(cx)
        error = compute_error(cx, "GREEN")

        # =====================================
        # PID CONTROL
        # =====================================

        steering_value = pid.compute(error)

        # Clamp steering
        steering_value = max(-30, min(30, steering_value))

        # =====================================
        # VISUALIZATION
        # =====================================

        # Tracking point
        cv2.circle(
            roi,
            (cx, cy),
            8,
            (255, 255, 0),
            -1
        )

        # Angle display
        cv2.putText(
            roi,
            f"{angle:.1f} deg",
            (cx, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2
        )

        # Object label
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
    # DISPLAY STEERING VALUE
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

    # =====================================
    # DISPLAY WINDOWS
    # =====================================

    cv2.imshow("Frame", frame)
    cv2.imshow("ROI", roi)
    cv2.imshow("Red Mask", red_mask)
    cv2.imshow("Green Mask", green_mask)

    # =====================================
    # EXIT
    # =====================================

    if cv2.waitKey(1) == 27:
        break

# =====================================
# CLEANUP
# =====================================

cap.release()
cv2.destroyAllWindows()