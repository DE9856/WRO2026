import cv2
from config.hsv_config import (
    RED_LOWER1, RED_UPPER1, RED_LOWER2, RED_UPPER2,
    GREEN_LOWER, GREEN_UPPER,
    MAGENTA_LOWER, MAGENTA_UPPER,
    ORANGE_LOWER, ORANGE_UPPER,
    BLUE_LOWER, BLUE_UPPER,
    BLACK_LOWER, BLACK_UPPER,
)


def get_red_mask(hsv):
    # Red wraps hue 0 in OpenCV's 0-179 scale, so it's two ranges OR'd together.
    mask1 = cv2.inRange(hsv, RED_LOWER1, RED_UPPER1)
    mask2 = cv2.inRange(hsv, RED_LOWER2, RED_UPPER2)
    return cv2.bitwise_or(mask1, mask2)


def get_green_mask(hsv):
    return cv2.inRange(hsv, GREEN_LOWER, GREEN_UPPER)


def get_magenta_mask(hsv):
    return cv2.inRange(hsv, MAGENTA_LOWER, MAGENTA_UPPER)


def get_orange_mask(hsv):
    return cv2.inRange(hsv, ORANGE_LOWER, ORANGE_UPPER)


def get_blue_mask(hsv):
    return cv2.inRange(hsv, BLUE_LOWER, BLUE_UPPER)


def get_black_mask(hsv):
    """Track walls (interior + exterior, both black per §13.4/§13.6) —
    used by camera/corridor.py for Open Challenge wall-centering steering."""
    return cv2.inRange(hsv, BLACK_LOWER, BLACK_UPPER)


def get_all_masks(hsv):
    """Convenience — every tracked colour in one call, keyed by name."""
    return {
        "RED":     get_red_mask(hsv),
        "GREEN":   get_green_mask(hsv),
        "MAGENTA": get_magenta_mask(hsv),
        "ORANGE":  get_orange_mask(hsv),
        "BLUE":    get_blue_mask(hsv),
        "BLACK":   get_black_mask(hsv),
    }
