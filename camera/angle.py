# =====================================
# OV5647 (Pi Camera v1.3) horizontal FOV
# is ~54 degrees, NOT 60.
# FRAME_WIDTH must match ROI width:
#   ROI = frame[180:480, 80:560]
#   ROI width = 560 - 80 = 480 px  ✓
# =====================================

FRAME_WIDTH   = 480
CAMERA_FOV    = 54      # corrected for OV5647
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