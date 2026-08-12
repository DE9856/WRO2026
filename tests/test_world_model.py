"""
tests/test_world_model.py
WRO 2026 Future Engineers — end-to-end integration test for the
camera -> seat_estimator -> section_observer -> WorldModel pipeline.

This replaces the previous version of this file, which called an API
(WorldModel(), Obstacle, add_obstacle(), print_state()) that no longer
exists in world_model/world.py or world_model/obstacle.py — it would
have raised ImportError immediately. This version tests the CURRENT
pipeline end to end, using synthetic detections shaped exactly like
camera/contours.py::detect_objects() output, so no camera or hardware
is required to run it.

Run from the repo root:
    python3 -m tests.test_world_model
"""

from world_model.obstacle import RED, GREEN, EMPTY, CARD_CATALOG
from world_model.world import WorldModel
from world_model.section_observer import SectionObserver

ROI_WIDTH = 300


def _synthetic_detection(cx: int, distance_cm: float) -> dict:
    """Builds a detection dict shaped like camera/contours.py's output,
    with only the fields seat_estimator.py actually reads."""
    return {"cx": cx, "distance": distance_cm}


def test_full_pipeline_single_section():
    """
    Simulates driving through one straightforward section that matches
    a real WRO card (card_13: TR=GREEN, BL=GREEN — see CARD_CATALOG),
    frame by frame, and confirms the finished seat_vector round-trips
    through WorldModel.observe() into a real card_id.
    """
    observer = SectionObserver()

    # A few frames approaching the section: TR pillar visible far (top),
    # BL pillar visible near (bottom) — consistent across frames, like a
    # real approach would look once the robot is close enough to see both.
    for _ in range(6):
        green_dets = [
            _synthetic_detection(cx=290, distance_cm=80.0),  # TR, far
            _synthetic_detection(cx=10, distance_cm=20.0),   # BL, near
        ]
        observer.update(red_detections=[], green_detections=green_dets, roi_width=ROI_WIDTH)

    seat_vector = observer.finalize(min_votes=2)
    assert seat_vector == CARD_CATALOG[13], seat_vector

    wm = WorldModel(excluded_color=RED)
    card_id = wm.observe("section_1", seat_vector, confidence=observer.confidence())
    assert card_id == 13, f"expected card_13, got {card_id}"
    assert wm.world_state["section_1"] == "card_13"
    print("  [PASS] full pipeline: frames -> seat_vector -> WorldModel.observe() -> card_13")


def test_empty_section_round_trip():
    """A section with no pillars at all should classify as all-EMPTY and
    still be a legal (single-sign-range... actually all-empty is not a
    real card) — WorldModel should correctly report no match rather than
    silently accepting a vector that isn't a real card."""
    observer = SectionObserver()
    for _ in range(4):
        observer.update(red_detections=[], green_detections=[], roi_width=ROI_WIDTH)

    seat_vector = observer.finalize(min_votes=1)
    assert seat_vector == [EMPTY] * 6

    wm = WorldModel(excluded_color=RED)
    card_id = wm.observe("section_2", seat_vector, confidence=observer.confidence())
    assert card_id is None, "an all-empty vector matches no real WRO card and must not commit"
    assert wm.world_state["section_2"] is None
    print("  [PASS] a section with no detections does not falsely commit a card")


def test_two_sections_share_deck_without_replacement():
    """Confirms the without-replacement constraint survives the full
    pipeline across two different sections in the same round."""
    wm = WorldModel(excluded_color=GREEN)

    obs1 = SectionObserver()
    for _ in range(5):
        obs1.update(
            red_detections=[_synthetic_detection(cx=10, distance_cm=80.0)],  # TL, far
            green_detections=[],
            roi_width=ROI_WIDTH,
        )
    vec1 = obs1.finalize(min_votes=2)
    card1 = wm.observe("section_1", vec1, confidence=obs1.confidence())
    assert card1 is not None, "single-pillar TL card should match something in the catalog"

    obs2 = SectionObserver()
    for _ in range(5):
        obs2.update(
            red_detections=[_synthetic_detection(cx=290, distance_cm=80.0)],  # TR, far
            green_detections=[],
            roi_width=ROI_WIDTH,
        )
    vec2 = obs2.finalize(min_votes=2)
    card2 = wm.observe("section_2", vec2, confidence=obs2.confidence())
    assert card2 is not None
    assert card1 != card2, "different seat vectors must not resolve to the same drawn card"
    assert card1 not in wm.deck.candidates()
    assert card2 not in wm.deck.candidates()
    print("  [PASS] two sections observed through the pipeline stay consistent with one shared deck")


def run_all():
    print("Running tests/test_world_model.py (integration)...")
    test_full_pipeline_single_section()
    test_empty_section_round_trip()
    test_two_sections_share_deck_without_replacement()
    print("All tests/test_world_model.py tests passed.")


if __name__ == "__main__":
    run_all()
