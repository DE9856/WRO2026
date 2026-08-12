"""
HSV colour ranges for the WRO 2026 vision pipeline.

Tracked colours:
  RED       — obstacle pillar                (Camera Guide §5, rule §13.21)
  GREEN     — obstacle pillar                (Camera Guide §5, rule §13.22)
  MAGENTA   — parking-lot boundary markers    (Camera Guide §5, rule §13.27)
  ORANGE    — corner/track boundary line      (Overall Guide §06)
  BLUE      — corner/track boundary line      (Overall Guide §06)

Defaults below are STARTING POINTS taken from the two guides — they are
NOT guaranteed to match your camera, your printed pillars, or your venue's
lighting. Run `python3 hsv_tuner.py` on the actual robot, under the
actual competition (or practice) lighting, and save each colour.

Tuned values are written to config/hsv_ranges.json, which this file loads
and overlays on top of the defaults below automatically. Nothing here
needs to be hand-edited — delete hsv_ranges.json to fall back to defaults.
"""

import json
import os
import numpy as np

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TUNED_FILE = os.path.join(_THIS_DIR, "hsv_ranges.json")

# =====================================
# DEFAULTS
# =====================================
# RED and MAGENTA use two/one range(s) already centred on the official
# WRO RGB targets converted to HSV (Camera Guide §5). ORANGE and BLUE
# use the hue bands from the Overall Guide §06 with conservative
# S/V floors — tune these floors first, they're the most venue-dependent.

_DEFAULTS = {
    # Red wraps hue 0 in OpenCV's 0-179 scale, so it needs two ranges
    # combined with OR (see camera/hsv.py::get_red_mask).
    "RED": [
        {"lower": [0, 120, 70],   "upper": [10, 255, 255]},
        {"lower": [170, 120, 70], "upper": [180, 255, 255]},
    ],
    "GREEN": [
        {"lower": [40, 70, 70], "upper": [90, 255, 255]},
    ],
    "MAGENTA": [
        {"lower": [140, 80, 80], "upper": [170, 255, 255]},
    ],
    "ORANGE": [
        {"lower": [8, 100, 100], "upper": [20, 255, 255]},
    ],
    "BLUE": [
        {"lower": [100, 100, 70], "upper": [130, 255, 255]},
    ],
    # BLACK — track walls (interior + exterior, rule §13.4/§13.6 both black).
    # Used by camera/corridor.py (Gap #1 fix: Open Challenge steering
    # fallback) — walls are low-Value regardless of hue, so this is a
    # V-ceiling threshold rather than a hue band like the others. The S
    # ceiling excludes strongly-saturated dark colours (e.g. deep red in
    # shadow) from being misread as wall. Tune the V ceiling first — it's
    # the most lighting-dependent value here.
    "BLACK": [
        {"lower": [0, 0, 0], "upper": [180, 90, 60]},
    ],
}

COLOR_ORDER = ["RED", "GREEN", "MAGENTA", "ORANGE", "BLUE", "BLACK"]


def _load_tuned():
    if os.path.exists(_TUNED_FILE):
        try:
            with open(_TUNED_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[hsv_config] WARNING: could not read {_TUNED_FILE} ({e}); using defaults")
    return {}


def _merge(defaults, tuned):
    merged = {k: v for k, v in defaults.items()}
    merged.update(tuned)
    return merged


_RANGES = _merge(_DEFAULTS, _load_tuned())


def _arr(range_dict):
    return np.array(range_dict["lower"]), np.array(range_dict["upper"])


def get_ranges(color_name):
    """Return the list of {lower, upper} dicts currently active for a colour."""
    return _RANGES[color_name.upper()]


def save_ranges(color_name, ranges):
    """
    Persist tuned ranges for a colour to config/hsv_ranges.json.
    ranges: list of {"lower": [h, s, v], "upper": [h, s, v]} dicts.
    Picked up automatically next time this module is imported
    (e.g. next run of main.py) — no restart-proofing needed beyond that.
    """
    tuned = _load_tuned()
    tuned[color_name.upper()] = ranges
    with open(_TUNED_FILE, "w") as f:
        json.dump(tuned, f, indent=2)
    print(f"[hsv_config] Saved {color_name.upper()} -> {_TUNED_FILE}")


def reload():
    """Re-read hsv_ranges.json + defaults and refresh the module-level constants below."""
    global _RANGES
    global RED_LOWER1, RED_UPPER1, RED_LOWER2, RED_UPPER2
    global GREEN_LOWER, GREEN_UPPER
    global MAGENTA_LOWER, MAGENTA_UPPER
    global ORANGE_LOWER, ORANGE_UPPER
    global BLUE_LOWER, BLUE_UPPER
    global BLACK_LOWER, BLACK_UPPER

    _RANGES = _merge(_DEFAULTS, _load_tuned())

    RED_LOWER1, RED_UPPER1 = _arr(_RANGES["RED"][0])
    RED_LOWER2, RED_UPPER2 = _arr(_RANGES["RED"][1])
    GREEN_LOWER, GREEN_UPPER = _arr(_RANGES["GREEN"][0])
    MAGENTA_LOWER, MAGENTA_UPPER = _arr(_RANGES["MAGENTA"][0])
    ORANGE_LOWER, ORANGE_UPPER = _arr(_RANGES["ORANGE"][0])
    BLUE_LOWER, BLUE_UPPER = _arr(_RANGES["BLUE"][0])
    BLACK_LOWER, BLACK_UPPER = _arr(_RANGES["BLACK"][0])


# =====================================
# NAMED CONSTANTS
# (what the rest of the codebase — camera/hsv.py etc. — actually imports)
# =====================================

RED_LOWER1, RED_UPPER1 = _arr(_RANGES["RED"][0])
RED_LOWER2, RED_UPPER2 = _arr(_RANGES["RED"][1])

GREEN_LOWER, GREEN_UPPER = _arr(_RANGES["GREEN"][0])

MAGENTA_LOWER, MAGENTA_UPPER = _arr(_RANGES["MAGENTA"][0])

ORANGE_LOWER, ORANGE_UPPER = _arr(_RANGES["ORANGE"][0])

BLUE_LOWER, BLUE_UPPER = _arr(_RANGES["BLUE"][0])

BLACK_LOWER, BLACK_UPPER = _arr(_RANGES["BLACK"][0])
