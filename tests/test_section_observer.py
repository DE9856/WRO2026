"""
tests/test_section_observer.py
WRO 2026 Future Engineers — pytest cases for world_model/section_observer.py.

H.28 FIX: converted from section_observer.py's in-module _run_tests()
into real pytest test_* functions. No functional change.
"""

from world_model.obstacle import EMPTY, RED, GREEN, SEAT_COUNT, TL, TR, BL
from world_model.section_observer import SectionObserver

ROI_W = 300


def test_consistent_multiframe_observation_finalizes_correctly():
    """A clean two-pillar card (card_13: TR=GREEN, BL=GREEN) observed
    consistently across several frames finalizes correctly."""
    obs = SectionObserver()
    for _ in range(5):
        green_dets = [
            {"cx": 290, "distance": 80.0},  # TR, far
            {"cx": 10, "distance": 20.0},   # BL, near
        ]
        obs.update(red_detections=[], green_detections=green_dets, roi_width=ROI_W)
    vector = obs.finalize()
    assert vector == [0, 0, GREEN, GREEN, 0, 0], vector


def test_stray_misdetection_filtered_by_min_votes():
    obs = SectionObserver()
    obs.update(red_detections=[{"cx": 150, "distance": 80.0}],  # 1 stray vote at TC
               green_detections=[], roi_width=ROI_W)
    vector = obs.finalize(min_votes=2)
    assert vector == [EMPTY] * SEAT_COUNT, vector


def test_reset_clears_accumulated_votes():
    obs = SectionObserver()
    obs.update(red_detections=[{"cx": 10, "distance": 80.0}], green_detections=[], roi_width=ROI_W)
    obs.reset()
    assert obs.finalize(min_votes=1) == [EMPTY] * SEAT_COUNT
    assert obs.frames_seen() == 0


def test_conflicting_votes_resolve_by_majority():
    obs = SectionObserver()
    for _ in range(3):
        obs.update(red_detections=[{"cx": 10, "distance": 80.0}], green_detections=[], roi_width=ROI_W)
    obs.update(red_detections=[], green_detections=[{"cx": 10, "distance": 80.0}], roi_width=ROI_W)
    vector = obs.finalize(min_votes=1)
    assert vector[TL] == RED, "3 red votes vs 1 green vote should resolve to RED"


def test_confidence_reflects_whether_votes_cast():
    obs = SectionObserver()
    assert obs.confidence() == 0.0
    obs.update(red_detections=[{"cx": 10, "distance": 80.0}], green_detections=[], roi_width=ROI_W)
    assert obs.confidence() > 0.0
