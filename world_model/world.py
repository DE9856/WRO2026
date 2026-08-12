"""
world.py
WRO 2026 Future Engineers — Top-level constrained-state world tracker.

Owns the WorldModel: the persistent track memory (world_state dict of
"section_N": "card_M"), confidence tracking, safe re-observation / conflict
handling, deliberate correction, and lap counting. Delegates all
card/pillar-configuration knowledge to obstacle.py (Deck, match_config,
CARD_CATALOG) so this file stays focused purely on "what do we currently
believe about the track" rather than "what are the legal card configs."

world_state shape (matches camera_processing_guide.html exactly):
    {"section_1": "card_17", "section_2": "card_4", ...,
     "parking_section": "section_2"}
"""

from __future__ import annotations
from typing import Optional

from world_model.obstacle import RED, GREEN, Deck, match_config, CARD_CATALOG  # noqa: F401


class WorldModel:
    SECTION_KEYS = ["section_1", "section_2", "section_3", "section_4"]

    def __init__(self, excluded_color: int):
        self.deck = Deck(excluded_color)
        self.world_state: dict[str, Optional[str]] = {k: None for k in self.SECTION_KEYS}
        self.world_state["parking_section"] = None
        self.confidence: dict[str, float] = {k: 0.0 for k in self.SECTION_KEYS}
        self.lap = 1

    def _validate_section_key(self, section_key: str) -> None:
        """
        Shared guard used by every public method that takes a section_key.
        Without this, a typo like 'section_5' silently creates a stray dict
        entry instead of failing — the world_state dict has no built-in
        schema, so nothing else would catch it.
        """
        if section_key not in self.SECTION_KEYS:
            raise ValueError(f"unknown section_key {section_key!r} — must be one of {self.SECTION_KEYS}")

    def set_parking_section(self, section_key: str) -> None:
        self._validate_section_key(section_key)
        self.world_state["parking_section"] = section_key

    def observe(
        self,
        section_key: str,
        seat_vector: list[int],
        confidence: float = 1.0,
        min_confidence: float = 0.0,
    ) -> Optional[int]:
        """
        Feed a freshly-detected seat vector for a section. Matches only
        against cards still remaining in the deck (without-replacement
        constraint), commits the match, and updates world_state.

        SAFE RE-OBSERVATION: sections get looked at more than once by design
        (Lap 1 maps cautiously, Lap 2 validates the same sections). Calling
        observe() again on an already-confirmed section is handled as
        follows, instead of blindly confirming a second card and corrupting
        the deck:
          - If the new vector matches the ALREADY-confirmed card's vector,
            this is just a confirmation: confidence is bumped (max of old
            and new) and the same card_id is returned. No deck change.
          - If the new vector does NOT match, this is a validation conflict
            (bad frame, misdetection, or a genuinely wrong earlier match).
            Nothing is overwritten automatically — silently reassigning
            would release/lose track of which card is actually where.
            Returns None. Use correct_section() below if you deliberately
            want to override a confirmed section.

        CONFIDENCE GATE: if confidence < min_confidence, the observation is
        treated as too unreliable to commit (returns None, no state change).
        Default min_confidence=0.0 preserves old behaviour (always commit
        on any match) until frame-voting supplies real confidence values.

        NOTE: WRO's official card sheet has intentional duplicate vectors
        ("Duplications of some of the cards is intentional" — Fig 8c). So
        multiple card_ids can share the same seat vector. That's fine: for
        DRIVING purposes only the seat_vector matters (where the pillars
        are), not which numbered card produced it. When several remaining
        cards match, we deterministically commit to the lowest card_id —
        since they're vector-identical, this has zero effect on future
        matching or on what the robot needs to do in that section; it just
        keeps logs/debugging reproducible.

        Returns the matched card_id, or None if no remaining card matches,
        confidence was below threshold, or a validation conflict occurred.
        """
        self._validate_section_key(section_key)

        if confidence < min_confidence:
            return None

        already = self.world_state.get(section_key)
        if already is not None:
            existing_card_id = int(already.split("_")[1])
            existing_vector = CARD_CATALOG.get(existing_card_id)
            if existing_vector == list(seat_vector):
                # Re-confirmation of the same section: bump confidence, no deck change.
                self.confidence[section_key] = max(self.confidence[section_key], confidence)
                return existing_card_id
            # Mismatch against an already-confirmed section: don't corrupt the
            # deck by silently confirming a second card here. Caller should
            # inspect this and use correct_section() if an override is intended.
            return None

        matches = match_config(seat_vector, self.deck.candidates())

        if matches:
            card_id = min(matches)  # deterministic — see NOTE above
            self.deck.confirm(card_id)
            self.world_state[section_key] = f"card_{card_id}"
            self.confidence[section_key] = confidence
            return card_id

        # No match at all — don't commit, let caller re-observe (Lap 1/2)
        return None

    def correct_section(self, section_key: str, seat_vector: list[int], confidence: float = 1.0) -> Optional[int]:
        """
        Deliberately override an already-confirmed section with a new
        detection — e.g. Lap 2 validation strongly disagrees with the Lap 1
        read and you've decided to trust the new frame. Releases the old
        card back into the deck's remaining pool before confirming the new
        one, so predict() for other sections stays correct.

        Returns the newly matched card_id, or None if no remaining (or just
        released) card matches seat_vector.
        """
        self._validate_section_key(section_key)

        already = self.world_state.get(section_key)
        if already is not None:
            old_card_id = int(already.split("_")[1])
            self.deck.release(old_card_id)
            self.world_state[section_key] = None
            self.confidence[section_key] = 0.0

        return self.observe(section_key, seat_vector, confidence=confidence)

    def unresolved_sections(self) -> list[str]:
        """Section keys that haven't been confirmed yet (excludes parking_section)."""
        return [k for k in self.SECTION_KEYS if self.world_state[k] is None]

    def predict(self, section_key: str) -> set[int]:
        """
        For a section not yet observed, return the set of cards that are
        still possible given what's already been confirmed elsewhere.
        This is the without-replacement predictive edge: as more sections
        get confirmed, this set shrinks.
        """
        self._validate_section_key(section_key)
        if self.world_state.get(section_key) is not None:
            cid = int(self.world_state[section_key].split("_")[1])
            return {cid}
        return self.deck.candidates()

    def advance_lap(self) -> None:
        self.lap += 1

    def is_fully_mapped(self) -> bool:
        return all(self.world_state[k] is not None for k in self.SECTION_KEYS)

    def summary(self) -> dict:
        return {
            "lap": self.lap,
            "world_state": dict(self.world_state),
            "confidence": dict(self.confidence),
            "remaining_candidates": len(self.deck.remaining),
        }


# ---------------------------------------------------------------------------
# Self-test / simulation — run a scripted fake race before wiring in
# the real camera pipeline.
# ---------------------------------------------------------------------------
def _simulate():
    # Suppose the coin toss fixed section_1 as the lone-sign section, colored RED.
    wm = WorldModel(excluded_color=RED)
    wm.set_parking_section("section_1")

    print("Deck size after exclusion:", len(wm.deck.remaining))

    # Fake "detections" for lap 1 — just grab real catalog vectors so they match.
    v2 = CARD_CATALOG[next(iter(wm.deck.candidates()))]
    result = wm.observe("section_2", v2, confidence=0.8)
    print("section_2 matched ->", result)

    remaining_after = wm.deck.candidates()
    v3 = CARD_CATALOG[next(iter(remaining_after))]
    result = wm.observe("section_3", v3, confidence=0.8)
    print("section_3 matched ->", result)

    print("Prediction for unobserved section_4 (candidate count):",
          len(wm.predict("section_4")))
    print(wm.summary())



if __name__ == "__main__":
    _simulate()
