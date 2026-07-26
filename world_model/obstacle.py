"""
obstacle.py
WRO 2026 Future Engineers — Traffic-sign / pillar configuration knowledge.

Owns:
  - The 36-card catalog (Figure 8c) mapping card_id -> seat vector, with
    integrity checks that fail loud at import time if the hand-transcribed
    table is broken.
  - The Deck: without-replacement draw logic per WRO rules §8 step 3, plus
    release() so a wrongly-confirmed card can be put back cleanly.
  - match_config(): turning a detected seat vector into candidate card_ids.

Data conventions (kept identical to camera_processing_guide.html §14A):
  - Seat state:   0 = EMPTY, 1 = RED, 2 = GREEN
  - Seat vector:  6 elements, one per traffic-sign seat in a straightforward
                  section (4 T-intersections + 2 X-intersections, WRO Game
                  Rules 2026 §5 / Figure 3). REAL Figure 8c geometry: each
                  card has 2 horizontal dashed lines (top/bottom) and 1
                  vertical dashed line down the center, giving 3 x-positions
                  per line (left edge, center, right edge). Order convention
                  used here (transcribed directly from the rulebook figure):

                      index 0 = TL (top line,    left edge)
                      index 1 = TC (top line,    center)   <- X-intersection
                      index 2 = TR (top line,    right edge)
                      index 3 = BL (bottom line, left edge)
                      index 4 = BC (bottom line, center)   <- X-intersection
                      index 5 = BR (bottom line, right edge)

                  This ordering is OUR choice (WRO doesn't number seats), but
                  it must stay consistent everywhere — camera ROI extraction
                  must fill the vector in this same TL,TC,TR,BL,BC,BR order.

                  >>> ASSUMPTION FLAG <<<
                  "top" = the entrance edge of the section / "bottom" = the
                  exit edge is inferred from the entry lines drawn in
                  Figure 3 and has NOT been independently confirmed against
                  the physical field or camera mount. Re-check this the
                  first time you calibrate against a real section — if it's
                  backwards, reverse index groups (0,1,2)<->(3,4,5)
                  everywhere and re-run.

CARD_CATALOG below is the real 36 seat vectors, transcribed by hand from
WRO's official Figure 8c ("36 cards with position of traffic signs within a
section"). Several cards are intentionally duplicate vectors:
  - single-sign duplicates: card_11 == card_5, card_12 == card_6 (both TR)
  - two-sign duplicates:    14≡16, 15≡17, 20≡22, 21≡23, 26≡28, 27≡29,
                             32≡34, 33≡35
This matches the rulebook's own note under Figure 8c that "Duplications of
some of the cards is intentional," so it's expected, not a transcription
error. _make_placeholder_catalog() below is kept only as a fallback for
quick smoke-testing without the real data; it is NOT called by default.
"""

from __future__ import annotations
import random
from typing import Optional

EMPTY, RED, GREEN = 0, 1, 2
SEAT_COUNT = 6

# Seat index shorthand: TL,TC,TR,BL,BC,BR -> 0..5
TL, TC, TR, BL, BC, BR = 0, 1, 2, 3, 4, 5

# ---------------------------------------------------------------------------
# 1. CARD CATALOG — real transcription from Figure 8c
# ---------------------------------------------------------------------------
# card_id (1-36) -> 6-element seat vector, order [TL, TC, TR, BL, BC, BR].
# Cards 1-10 carry a single sign (9=BC-green, 10=BC-red — the two cards the
# excluded_color rule removes one of); cards 11-36 carry one or two signs.
CARD_CATALOG: dict[int, list[int]] = {}


def fill_card(card_id: int, seats: list[int], *, overwrite: bool = False) -> None:
    """
    Register one card's seat vector.

    Validates seats has the right length AND that every value is a legal
    seat state (EMPTY/RED/GREEN) — catches typos like a stray 3 that would
    otherwise sit silently in the catalog and just never match any real
    detection.

    Raises if card_id is already registered, unless overwrite=True. This is
    the main defence against the most realistic failure mode for a hand-
    transcribed 36-entry catalog: accidentally re-typing the same card
    number twice, silently clobbering the first (correct) entry.
    """
    if len(seats) != SEAT_COUNT:
        raise ValueError(f"card_{card_id}: expected {SEAT_COUNT} seats, got {len(seats)}")
    bad = [s for s in seats if s not in (EMPTY, RED, GREEN)]
    if bad:
        raise ValueError(f"card_{card_id}: invalid seat value(s) {bad} — must be EMPTY/RED/GREEN (0/1/2)")
    if card_id in CARD_CATALOG and not overwrite:
        raise ValueError(
            f"card_{card_id} is already registered as {CARD_CATALOG[card_id]} — "
            f"refusing to silently overwrite. Pass overwrite=True if this is intentional."
        )
    CARD_CATALOG[card_id] = list(seats)


def _make_real_catalog() -> None:
    """Fills CARD_CATALOG with the real 36 vectors transcribed from Figure 8c."""

    def seat(*pairs: tuple[int, int]) -> list[int]:
        v = [EMPTY] * SEAT_COUNT
        for idx, color in pairs:
            v[idx] = color
        return v

    fill_card(1,  seat((TL, GREEN)))
    fill_card(2,  seat((TL, RED)))
    fill_card(3,  seat((TC, GREEN)))
    fill_card(4,  seat((TC, RED)))
    fill_card(5,  seat((TR, GREEN)))
    fill_card(6,  seat((TR, RED)))
    fill_card(7,  seat((BL, GREEN)))
    fill_card(8,  seat((BL, RED)))
    fill_card(9,  seat((BC, GREEN)))
    fill_card(10, seat((BC, RED)))
    fill_card(11, seat((TR, GREEN)))
    fill_card(12, seat((TR, RED)))
    fill_card(13, seat((TR, GREEN), (BL, GREEN)))
    fill_card(14, seat((TR, RED),   (BL, GREEN)))
    fill_card(15, seat((TR, GREEN), (BL, RED)))
    fill_card(16, seat((TR, RED),   (BL, GREEN)))
    fill_card(17, seat((TR, GREEN), (BL, RED)))
    fill_card(18, seat((TR, RED),   (BL, RED)))
    fill_card(19, seat((TL, GREEN), (BR, GREEN)))
    fill_card(20, seat((TL, GREEN), (BR, RED)))
    fill_card(21, seat((TL, RED),   (BR, GREEN)))
    fill_card(22, seat((TL, GREEN), (BR, RED)))
    fill_card(23, seat((TL, RED),   (BR, GREEN)))
    fill_card(24, seat((TL, RED),   (BR, RED)))
    fill_card(25, seat((TL, GREEN), (TR, GREEN)))
    fill_card(26, seat((TL, GREEN), (TR, RED)))
    fill_card(27, seat((TL, RED),   (TR, GREEN)))
    fill_card(28, seat((TL, GREEN), (TR, RED)))
    fill_card(29, seat((TL, RED),   (TR, GREEN)))
    fill_card(30, seat((TL, RED),   (TR, RED)))
    fill_card(31, seat((BL, GREEN), (BR, GREEN)))
    fill_card(32, seat((BL, GREEN), (BR, RED)))
    fill_card(33, seat((BL, RED),   (BR, GREEN)))
    fill_card(34, seat((BL, GREEN), (BR, RED)))
    fill_card(35, seat((BL, RED),   (BR, GREEN)))
    fill_card(36, seat((BL, RED),   (BR, RED)))


_make_real_catalog()


def _verify_catalog_integrity() -> None:
    """
    Fails LOUD and IMMEDIATE at import time if the hand-transcribed catalog
    is broken, instead of letting a bad card silently produce wrong matches
    mid-competition. This is the single most valuable check in this file
    given the catalog was typed by hand.
    """
    assert len(CARD_CATALOG) == 36, f"expected 36 cards, got {len(CARD_CATALOG)}"
    assert set(CARD_CATALOG.keys()) == set(range(1, 37)), "card ids must be exactly 1..36"

    for cid, v in CARD_CATALOG.items():
        assert len(v) == SEAT_COUNT, f"card_{cid} has wrong length"
        assert all(x in (EMPTY, RED, GREEN) for x in v), f"card_{cid} has an invalid seat value: {v}"
        n_signs = sum(1 for x in v if x != EMPTY)
        if cid <= 10:
            assert n_signs == 1, f"card_{cid} (single-sign range) has {n_signs} signs"
        elif cid in (11, 12):
            # Confirmed against the rulebook figure and against the user-supplied
            # card list: cards 11/12 are intentional single-sign duplicates of
            # cards 5/6 (both TR), breaking the "11-36 have two signs" pattern
            # that every other card in this range follows.
            assert n_signs in (1, 2), f"card_{cid} has {n_signs} signs — expected 1 or 2 (unconfirmed card)"
        else:
            assert n_signs == 2, f"card_{cid} (two-sign range) has {n_signs} signs"

    # Deck.confirm()'s exclusion logic hard-codes card_9 = single GREEN at BC,
    # card_10 = single RED at BC. If these ever change, exclusion silently
    # breaks, so pin it down explicitly here.
    assert CARD_CATALOG[9] == [EMPTY, EMPTY, EMPTY, EMPTY, GREEN, EMPTY], "card_9 must be the single BC-green card"
    assert CARD_CATALOG[10] == [EMPTY, EMPTY, EMPTY, EMPTY, RED, EMPTY], "card_10 must be the single BC-red card"


_verify_catalog_integrity()


def _make_placeholder_catalog() -> None:
    """
    OPTIONAL fallback only. Overwrites CARD_CATALOG with SYNTHETIC random
    vectors — useful only if you want to stress-test the matching logic
    against a fresh random deck. NOT called anywhere by default now that
    _make_real_catalog() has already populated CARD_CATALOG on import.
    DO NOT use this data for an actual competition robot.
    """
    rng = random.Random(42)
    for card_id in range(1, 37):
        seats = [EMPTY] * SEAT_COUNT
        n_signs = 1 if card_id <= 10 else 2
        positions = rng.sample(range(SEAT_COUNT), n_signs)
        color = RED if card_id % 2 == 0 else GREEN
        for p in positions:
            seats[p] = color if n_signs == 1 else rng.choice([RED, GREEN])
        fill_card(card_id, seats, overwrite=True)


# ---------------------------------------------------------------------------
# 2. DECK — models WRO rules §8 "Obstacle Challenge rounds" step 3:
#    one color's card (9 or 10) is removed, remaining 35 are drawn WITHOUT
#    replacement, one per remaining straightforward section, in clockwise
#    order. This lets the world model narrow down candidates for sections
#    it hasn't observed yet.
# ---------------------------------------------------------------------------
class Deck:
    def __init__(self, excluded_color: int):
        """
        excluded_color: RED or GREEN — the color of the single-sign section
        already fixed by the coin toss (its matching card, 9 or 10, is
        removed from the pool per the rules).
        """
        if excluded_color not in (RED, GREEN):
            raise ValueError("excluded_color must be RED or GREEN")
        excluded_card = 10 if excluded_color == RED else 9
        self.remaining: set[int] = {c for c in CARD_CATALOG if c != excluded_card}
        self.drawn: list[int] = []

    def candidates(self) -> set[int]:
        """Cards that could still legally appear in an unobserved section."""
        return set(self.remaining)

    def confirm(self, card_id: int) -> None:
        """Mark a card as drawn/observed — removes it from the remaining pool."""
        if card_id not in CARD_CATALOG:
            raise ValueError(f"card_{card_id} is not a real card in CARD_CATALOG")
        if card_id not in self.remaining:
            raise ValueError(f"card_{card_id} already drawn or was excluded")
        self.remaining.discard(card_id)
        self.drawn.append(card_id)

    def release(self, card_id: int) -> None:
        """
        Put a previously-confirmed card back into the remaining pool — used
        by WorldModel.correct_section() when deliberately overriding an
        earlier (wrong) match. Validated so a double-release or releasing a
        card that was never drawn can't silently inflate the deck.
        """
        if card_id not in CARD_CATALOG:
            raise ValueError(f"card_{card_id} is not a real card in CARD_CATALOG")
        if card_id in self.remaining:
            raise ValueError(f"card_{card_id} is already in the remaining pool — nothing to release")
        if card_id not in self.drawn:
            raise ValueError(f"card_{card_id} was never drawn — nothing to release")
        self.drawn.remove(card_id)
        self.remaining.add(card_id)


# ---------------------------------------------------------------------------
# 3. Config matcher — turn a detected seat vector into a card id (or a
#    shortlist of candidates if ambiguous / partially occluded).
# ---------------------------------------------------------------------------
def match_config(seat_vector: list[int], candidate_ids: Optional[set[int]] = None) -> list[int]:
    """
    Returns list of card_ids whose catalog vector matches seat_vector exactly.
    If candidate_ids is given, only checks those (use Deck.candidates() here
    during a live race so already-drawn cards can't match again).

    Empty result -> detection noise, or a genuinely malformed seat_vector
    (see the length/value validation below — that's checked separately so
    a real bug doesn't just masquerade as "no match, must be noise").

    Multiple results ARE expected and normal, not a bug: WRO's card sheet
    has intentional duplicate vectors (Fig 8c note), so several remaining
    card_ids can legitimately share the same seat layout. Callers (e.g.
    WorldModel.observe()) pick the lowest id deterministically — since
    duplicates are vector-identical, it has zero effect on driving.
    """
    if len(seat_vector) != SEAT_COUNT:
        raise ValueError(f"seat_vector must have length {SEAT_COUNT}, got {len(seat_vector)}")
    bad = [s for s in seat_vector if s not in (EMPTY, RED, GREEN)]
    if bad:
        raise ValueError(f"seat_vector has invalid value(s) {bad} — must be EMPTY/RED/GREEN (0/1/2)")

    pool = candidate_ids if candidate_ids is not None else CARD_CATALOG.keys()
    return [cid for cid in pool if CARD_CATALOG.get(cid) == list(seat_vector)]


# ---------------------------------------------------------------------------
# 4. Tests for obstacle.py's own responsibilities: catalog integrity,
#    fill_card overwrite protection, Deck confirm/release, and match_config
#    input validation.
# ---------------------------------------------------------------------------
def _run_tests():
    print("Running obstacle.py tests...")

    # --- Test 1: catalog integrity is provably correct (regression-proof,
    #     not just eyeballed once).
    assert len(CARD_CATALOG) == 36
    dupe_groups = {}
    for cid, v in CARD_CATALOG.items():
        dupe_groups.setdefault(tuple(v), []).append(cid)
    dupes = sorted(tuple(sorted(g)) for g in dupe_groups.values() if len(g) > 1)
    expected_dupes = [(5, 11), (6, 12), (14, 16), (15, 17), (20, 22), (21, 23), (26, 28), (27, 29), (32, 34), (33, 35)]
    assert dupes == sorted(expected_dupes), f"unexpected duplicate map: {dupes}"
    print("  [PASS] catalog integrity: 36 cards, duplicate map matches expected pattern")

    # --- Test 2: fill_card refuses to silently overwrite an existing card.
    try:
        fill_card(1, [GREEN, 0, 0, 0, 0, 0])
        raise AssertionError("fill_card should refuse to silently overwrite card_1")
    except ValueError:
        pass
    fill_card(1, [GREEN, 0, 0, 0, 0, 0], overwrite=True)  # explicit overwrite is fine
    fill_card(1, [GREEN, 0, 0, 0, 0, 0], overwrite=True)  # restore original card_1 exactly
    assert CARD_CATALOG[1] == [GREEN, 0, 0, 0, 0, 0]
    print("  [PASS] fill_card refuses silent overwrite, allows explicit overwrite=True")

    # --- Test 3: fill_card rejects invalid seat values and wrong length.
    try:
        fill_card(99, [0, 0, 0, 0, 0, 3])
        raise AssertionError("fill_card should reject an invalid seat value")
    except ValueError:
        pass
    try:
        fill_card(99, [0, 0, 0])
        raise AssertionError("fill_card should reject the wrong vector length")
    except ValueError:
        pass
    assert 99 not in CARD_CATALOG, "a rejected fill_card call must not leave a partial entry"
    print("  [PASS] fill_card rejects invalid seat values and wrong-length vectors")

    # --- Test 4: Deck confirm/release round-trips correctly, and rejects
    #     double-release or releasing a card that was never drawn.
    d = Deck(excluded_color=RED)
    assert len(d.candidates()) == 35, "excluding one color should leave 35 cards"
    d.confirm(13)
    assert 13 not in d.candidates()
    d.release(13)
    assert 13 in d.candidates()
    try:
        d.release(13)  # already released
        raise AssertionError("double-release should have raised")
    except ValueError:
        pass
    try:
        d.release(20)  # never drawn at all
        raise AssertionError("releasing a never-drawn card should have raised")
    except ValueError:
        pass
    print("  [PASS] Deck.confirm()/release() round-trip correctly and reject invalid releases")

    # --- Test 5: match_config raises on malformed input instead of quietly
    #     returning an empty list indistinguishable from real "no match".
    for bad_vector in ([1, 2, 0], [0, 0, 0, 0, 0, 5], [0, 0, 0, 0, 0]):
        try:
            match_config(bad_vector)
            raise AssertionError(f"match_config should have rejected malformed vector {bad_vector}")
        except ValueError:
            pass
    assert 13 in match_config(CARD_CATALOG[13])
    print("  [PASS] match_config rejects malformed vectors, matches valid ones")

    print("All obstacle.py tests passed.")


if __name__ == "__main__":
    _run_tests()