"""
tests/test_obstacle.py
WRO 2026 Future Engineers — pytest cases for world_model/obstacle.py.

H.28 FIX: this was previously a hand-rolled _run_tests()/assert block
inside world_model/obstacle.py itself, only runnable via
`python3 world_model/obstacle.py`. Converted to real pytest test_*
functions (cosmetic consolidation, no behavioural change) so `pytest`
discovers and runs it like every other test in this directory.
"""

import pytest

from world_model.obstacle import (
    RED, GREEN, CARD_CATALOG, fill_card, Deck, match_config,
)


def test_catalog_integrity_duplicate_map():
    """Catalog integrity is provably correct (regression-proof, not just
    eyeballed once): 36 cards, duplicate map matches the expected pattern."""
    assert len(CARD_CATALOG) == 36

    dupe_groups = {}
    for cid, v in CARD_CATALOG.items():
        dupe_groups.setdefault(tuple(v), []).append(cid)
    dupes = sorted(tuple(sorted(g)) for g in dupe_groups.values() if len(g) > 1)
    expected_dupes = [(5, 11), (6, 12), (14, 16), (15, 17), (20, 22),
                       (21, 23), (26, 28), (27, 29), (32, 34), (33, 35)]
    assert dupes == sorted(expected_dupes), f"unexpected duplicate map: {dupes}"


def test_fill_card_refuses_silent_overwrite():
    """fill_card refuses to silently overwrite an existing card, but
    allows an explicit overwrite=True."""
    with pytest.raises(ValueError):
        fill_card(1, [GREEN, 0, 0, 0, 0, 0])

    fill_card(1, [GREEN, 0, 0, 0, 0, 0], overwrite=True)
    fill_card(1, [GREEN, 0, 0, 0, 0, 0], overwrite=True)  # restore original card_1 exactly
    assert CARD_CATALOG[1] == [GREEN, 0, 0, 0, 0, 0]


def test_fill_card_rejects_invalid_seat_values_and_length():
    with pytest.raises(ValueError):
        fill_card(99, [0, 0, 0, 0, 0, 3])
    with pytest.raises(ValueError):
        fill_card(99, [0, 0, 0])
    assert 99 not in CARD_CATALOG, "a rejected fill_card call must not leave a partial entry"


def test_deck_confirm_release_round_trip():
    """Deck confirm/release round-trips correctly, and rejects
    double-release or releasing a card that was never drawn."""
    d = Deck(excluded_color=RED)
    assert len(d.candidates()) == 35, "excluding one color should leave 35 cards"

    d.confirm(13)
    assert 13 not in d.candidates()
    d.release(13)
    assert 13 in d.candidates()

    with pytest.raises(ValueError):
        d.release(13)  # already released
    with pytest.raises(ValueError):
        d.release(20)  # never drawn at all


def test_match_config_rejects_malformed_vectors():
    for bad_vector in ([1, 2, 0], [0, 0, 0, 0, 0, 5], [0, 0, 0, 0, 0]):
        with pytest.raises(ValueError):
            match_config(bad_vector)
    assert 13 in match_config(CARD_CATALOG[13])
