# =====================================
# Logitech C270 horizontal FOV.
# Logitech's published spec (55-60 deg) is the DIAGONAL FOV, not
# horizontal — the C270 doesn't publish a horizontal number.
# 60 deg is the commonly used approximation for the C270 in
# robotics/vision projects, but it's still an approximation.
# TODO: calibrate for real — point the camera at two marks a known
# distance apart at a known range, measure their pixel positions,
# and solve for the true horizontal FOV. Update CAMERA_FOV below.
#
# FRAME_WIDTH must match ROI width:
#   ROI = frame[180:480, 80:560]
#   ROI width = 560 - 80 = 480 px  ✓
# (Unaffected by the camera swap — still 640x480 capture.)
# =====================================

FRAME_WIDTH   = 480
CAMERA_FOV    = 60      # approx. for C270 — needs on-track calibration
CLEARANCE_PX  = 80      # pixel offset from pillar centre


def estimate_angle(cx):

    center_x = FRAME_WIDTH / 2
    offset   = cx - center_x
    angle    = (offset / center_x) * (CAMERA_FOV / 2)

    return round(angle, 2)


def compute_error(pillar_cx, color):

    center_x = FRAME_WIDTH / 2

    if color == "RED":
        target_x = pillar_cx - CLEARANCE_PX   # steer LEFT of red
    else:
        target_x = pillar_cx + CLEARANCE_PX   # steer RIGHT of green

    return target_x - center_x                # signed pixel error for PID