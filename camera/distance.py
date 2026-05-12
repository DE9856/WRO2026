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
# =====================================

FOCAL_LENGTH = 620

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