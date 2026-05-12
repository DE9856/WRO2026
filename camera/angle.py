import math


FRAME_WIDTH = 480
CAMERA_FOV = 60
CLEARANCE_PX = 80  # how many pixels to offset from pillar center

def estimate_angle(cx):
    center_x = FRAME_WIDTH / 2
    offset = cx - center_x
    angle = (offset / center_x) * (CAMERA_FOV / 2)
    return round(angle, 2)

def compute_error(pillar_cx, color):
    center_x = FRAME_WIDTH / 2
    if color == "RED":
        target_x = pillar_cx - CLEARANCE_PX  # steer LEFT of red
    else:
        target_x = pillar_cx + CLEARANCE_PX  # steer RIGHT of green
    return target_x - center_x              # signed pixel error for PID

