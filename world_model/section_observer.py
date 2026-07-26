"""
section_observer.py
WRO 2026 Future Engineers — accumulates per-frame seat classifications into
one confirmed seat_vector for whichever section is currently in view.

WHY THIS EXISTS
    A single camera frame almost never sees an entire straightforward
    section at once — the robot is forward-facing and the section is
    ~600-1000mm long. A pillar drifts across several frames as the robot
    approaches (far -> near, i.e. TOP row -> BOTTOM row in seat terms) and
    a mis-classified frame or two shouldn't corrupt the final vote.

    This class is the vote-counting accumulator that sits between
    seat_estimator.py (one frame -> zero or more (seat_index, color) pairs)
    and world_model.world.WorldModel.observe() (needs one finished 6-slot
    seat_vector for the whole section).

WHAT THIS DELIBERATELY DOES NOT DO
    - It does not decide WHEN a section starts or ends. That is a planner
      responsibility (current_section, lap count, driving direction —
      see world_model/vehicle_state.py). Call reset() when the planner
      says "we just entered a new section", and finalize() right before
      the planner advances to the next one.
    - It does not call WorldModel.observe() itself — it only produces the
      seat_vector. The caller decides the section_key and confidence.
"""

from __future__ import annotations

from world_model.obstacle import EMPTY, RED, GREEN, SEAT_COUNT
from world_model.seat_estimator import classify_detections, TOP_BOTTOM_SPLIT_CM


class SectionObserver:
    def __init__(self, split_cm: float = TOP_BOTTOM_SPLIT_CM):
        self.split_cm = split_cm
        self._votes: list[dict[int, int]] = [dict() for _ in range(SEAT_COUNT)]
        self._frames_seen = 0

    def reset(self) -> None:
        """Call when the planner signals entry into a new section."""
        self._votes = [dict() for _ in range(SEAT_COUNT)]
        self._frames_seen = 0

    def update(self, red_detections: list[dict], green_detections: list[dict],
               roi_width: int) -> None:
        """
        Feed one frame's worth of detections (camera/contours.py output,
        already split by colour as main.py already does for red_mask /
        green_mask). Safe to call every frame; a frame with no detections
        of either colour just increments the frame counter and votes
        nothing.
        """
        self._frames_seen += 1

        pairs = []
        if red_detections:
            pairs += classify_detections(red_detections, RED, roi_width, self.split_cm)
        if green_detections:
            pairs += classify_detections(green_detections, GREEN, roi_width, self.split_cm)

        for seat_index, color in pairs:
            bucket = self._votes[seat_index]
            bucket[color] = bucket.get(color, 0) + 1

    def frames_seen(self) -> int:
        return self._frames_seen

    def finalize(self, min_votes: int = 1) -> list[int]:
        """
        Collapse accumulated votes into a 6-element seat_vector suitable
        for WorldModel.observe(). Each seat independently takes whichever
        colour has the most votes (ties broken RED-first, arbitrarily —
        a genuine tie means the detection was unreliable either way and
        WorldModel.observe() will reject the vector entirely if it doesn't
        match a real card, which is the correct failure mode).

        A seat with fewer than min_votes total votes is treated as EMPTY
        — this is what filters out a single stray misdetection from
        putting a phantom pillar in an empty seat.
        """
        vector = [EMPTY] * SEAT_COUNT

        for seat_index, bucket in enumerate(self._votes):
            if not bucket:
                continue
            total_votes = sum(bucket.values())
            if total_votes < min_votes:
                continue
            # RED first on ties: sort by (-count, color) with RED < GREEN.
            best_color = min(bucket.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            vector[seat_index] = best_color

        return vector

    def confidence(self) -> float:
        """
        Rough confidence score in [0, 1] for the accumulated observation,
        based on how many frames contributed at least one vote. Callers
        can pass this straight into WorldModel.observe(confidence=...).
        This is a simple placeholder — refine once real on-track vote
        counts are available to calibrate against.
        """
        if self._frames_seen == 0:
            return 0.0
        voted_frames = sum(sum(bucket.values()) for bucket in self._votes)
        return min(1.0, voted_frames / max(self._frames_seen, 1))


# ---------------------------------------------------------------------------
# Self-test — synthetic multi-frame detection sequences, no camera needed.
# ---------------------------------------------------------------------------
def _run_tests():
    print("Running section_observer.py tests...")

    roi_w = 300

    # --- Test 1: a clean two-pillar card (card_13: TR=GREEN, BL=GREEN)
    #     observed consistently across several frames finalizes correctly.
    obs = SectionObserver()
    for _ in range(5):
        green_dets = [
            {"cx": 290, "distance": 80.0},  # TR, far
            {"cx": 10, "distance": 20.0},   # BL, near
        ]
        obs.update(red_detections=[], green_detections=green_dets, roi_width=roi_w)
    vector = obs.finalize()
    assert vector == [0, 0, GREEN, GREEN, 0, 0], vector
    print("  [PASS] consistent multi-frame observation finalizes to the right vector")

    # --- Test 2: a single stray misdetection in an otherwise-empty seat
    #     is filtered out by min_votes.
    obs = SectionObserver()
    obs.update(red_detections=[{"cx": 150, "distance": 80.0}],  # 1 stray vote at TC
               green_detections=[], roi_width=roi_w)
    vector = obs.finalize(min_votes=2)
    assert vector == [EMPTY] * SEAT_COUNT, vector
    print("  [PASS] a single stray vote is filtered out by min_votes")

    # --- Test 3: reset() clears accumulated votes.
    obs = SectionObserver()
    obs.update(red_detections=[{"cx": 10, "distance": 80.0}], green_detections=[], roi_width=roi_w)
    obs.reset()
    assert obs.finalize(min_votes=1) == [EMPTY] * SEAT_COUNT
    assert obs.frames_seen() == 0
    print("  [PASS] reset() clears votes and frame count")

    # --- Test 4: conflicting colour votes on the same seat resolve by majority.
    obs = SectionObserver()
    for _ in range(3):
        obs.update(red_detections=[{"cx": 10, "distance": 80.0}], green_detections=[], roi_width=roi_w)
    obs.update(red_detections=[], green_detections=[{"cx": 10, "distance": 80.0}], roi_width=roi_w)
    vector = obs.finalize(min_votes=1)
    assert vector[TL] == RED, "3 red votes vs 1 green vote should resolve to RED"
    print("  [PASS] conflicting votes on one seat resolve by majority")

    # --- Test 5: confidence() is 0 with no frames, and > 0 once fed.
    obs = SectionObserver()
    assert obs.confidence() == 0.0
    obs.update(red_detections=[{"cx": 10, "distance": 80.0}], green_detections=[], roi_width=roi_w)
    assert obs.confidence() > 0.0
    print("  [PASS] confidence() reflects whether any votes have been cast")

    print("All section_observer.py tests passed.")


if __name__ == "__main__":
    from world_model.obstacle import TL  # local import to avoid polluting module namespace
    _run_tests()
