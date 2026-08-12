# =====================================
# DISTANCE ESTIMATION VIA SIMILAR TRIANGLES
# =====================================
#
# WRO pillar dimensions:
#   50 x 50 x 100 mm
#
# Width is more stable than height because:
# - pillar top may be cropped
# - perspective affects height more
# - width remains visible longer
#
# Formula:
#   Distance = (Real Width * Focal Length) / Pixel Width
#
# IMPORTANT — camera swap (Pi Camera -> Logitech C270):
# FOCAL_LENGTH here is not the physical lens focal length in mm,
# it's the "focal length in pixels" derived from this specific
# camera+lens (sensor size, lens FOV, resolution all bake into it).
# The value below (620) was calibrated for the old Pi camera and
# is almost certainly wrong for the C270 — its lens/sensor geometry
# is different. Recalibrate with:
#   FOCAL_LENGTH = (pixel_width_measured * KNOWN_DISTANCE_MM) / REAL_PILLAR_WIDTH_MM
# i.e. place a pillar at a known, measured distance, read the
# pixel_width the pipeline reports (enable CALIBRATION_MODE below
# to print it), and solve for FOCAL_LENGTH. Repeat at 2-3 distances
# and average for a more reliable value. See calibrate_focal_length.py.
# =====================================

FOCAL_LENGTH = 1020      # TODO: recalibrate for the C270 — see note above

REAL_PILLAR_WIDTH_MM = 50.0

CALIBRATION_MODE = False


def estimate_distance(pixel_width):

    if pixel_width <= 0:
        return float("inf")

    if CALIBRATION_MODE:

        print(
            f"[CALIBRATION] pixel_width={pixel_width}"
        )

    distance_mm = (
        REAL_PILLAR_WIDTH_MM * FOCAL_LENGTH
    ) / pixel_width

    distance_cm = distance_mm / 10.0

    return round(distance_cm, 2)