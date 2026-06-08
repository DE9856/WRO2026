from picamera2 import Picamera2
import cv2

# =====================================
# CAMERA RESOLUTION
# Must be at least 560x480 for the
# ROI crop in main.py to work correctly
# =====================================

CAMERA_WIDTH  = 640
CAMERA_HEIGHT = 480

def init_camera():

    cam = Picamera2()

    config = cam.create_preview_configuration(
        main={
            "format": "BGR888",
            "size": (CAMERA_WIDTH, CAMERA_HEIGHT)
        }
    )

    cam.configure(config)

    # =====================================
    # LOCK WHITE BALANCE
    # OV5647 (v1.3) has no IR filter and
    # drifts under artificial lighting.
    # These gains work for most indoor setups.
    # Tune ColourGains=(r, b) if colours
    # look wrong on your specific unit.
    # =====================================

    cam.start()

    cam.set_controls({

    # Lock white balance
    "AwbEnable": False,

    # Tuned indoor gains
    "ColourGains": (1.4, 1.5),

    # Lock exposure
    "ExposureTime": 8000,

    # Lock sensor gain / ISO
    "AnalogueGain": 2.0
    })

    return cam


def read_frame(cam):

    frame = cam.capture_array()

    if frame is None:
        return None

    return frame


def release_camera(cam):

    cam.stop()
    cam.close()
