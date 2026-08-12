"""
tests/test_world.py
WRO 2026 Future Engineers — pytest cases for world_model/world.py.

H.28 FIX: converted from world_model/world.py's in-module _run_tests()
into real pytest test_* functions. No functional change.
"""

import pytest

from world_model.obstacle import RED, GREEN, CARD_CATALOG
from world_model.world import WorldModel


def test_reobservation_same_vector_confirms_without_deck_corruption():
    wm = WorldModel(excluded_color=RED)
    v = CARD_CATALOG[13]  # two-sign card, safe pick
    cid1 = wm.observe("section_2", v, confidence=0.6)
    remaining_after_first = len(wm.deck.remaining)
    cid2 = wm.observe("section_2", v, confidence=0.9)  # same vector again

    assert cid1 == cid2 == 13, "same-vector re-observation should confirm same card"
    assert len(wm.deck.remaining) == remaining_after_first, "deck should NOT shrink on re-confirmation"
    assert wm.confidence["section_2"] == 0.9, "confidence should bump to the higher value"


def test_conflicting_reobservation_is_rejected():
    wm = WorldModel(excluded_color=RED)
    wm.observe("section_2", CARD_CATALOG[13], confidence=0.6)
    remaining_before_conflict = len(wm.deck.remaining)
    result = wm.observe("section_2", CARD_CATALOG[18], confidence=0.9)  # different vector

    assert result is None, "conflicting re-observation should return None"
    assert wm.world_state["section_2"] == "card_13", "original confirmed card must be untouched"
    assert len(wm.deck.remaining) == remaining_before_conflict, "deck must not shrink on a rejected conflict"


def test_correct_section_overrides_cleanly():
    wm = WorldModel(excluded_color=RED)
    wm.observe("section_2", CARD_CATALOG[13], confidence=0.6)
    new_cid = wm.correct_section("section_2", CARD_CATALOG[18], confidence=0.95)

    assert new_cid == 18, "correct_section should confirm the new card"
    assert wm.world_state["section_2"] == "card_18"
    assert 13 in wm.deck.remaining, "old card must be released back into the deck"
    assert 18 not in wm.deck.remaining, "new card must be removed from the deck"


def test_confidence_below_threshold_is_not_committed():
    wm = WorldModel(excluded_color=RED)
    result = wm.observe("section_2", CARD_CATALOG[13], confidence=0.2, min_confidence=0.5)

    assert result is None, "low-confidence observation should be rejected"
    assert wm.world_state["section_2"] is None, "world_state must be untouched"


def test_unresolved_sections_tracks_confirmed_vs_unconfirmed():
    wm = WorldModel(excluded_color=RED)
    assert set(wm.unresolved_sections()) == set(wm.SECTION_KEYS)

    wm.observe("section_2", CARD_CATALOG[13], confidence=0.9)
    assert "section_2" not in wm.unresolved_sections()
    assert len(wm.unresolved_sections()) == 3


def test_invalid_section_key_is_rejected_everywhere():
    wm = WorldModel(excluded_color=RED)
    for bad_key in ("section_5", "Section_2", "", "parking_section"):
        with pytest.raises(ValueError):
            wm.observe(bad_key, CARD_CATALOG[13])
        with pytest.raises(ValueError):
            wm.predict(bad_key)
    assert "section_5" not in wm.world_state, "invalid key must never leak into world_state"


def test_full_mapping_reaches_is_fully_mapped():
    wm = WorldModel(excluded_color=GREEN)
    for key in wm.SECTION_KEYS:
        vec = CARD_CATALOG[next(iter(wm.deck.candidates()))]
        wm.observe(key, vec, confidence=0.9)

    assert wm.is_fully_mapped(), "all 4 sections observed, should be fully mapped"
    assert len(wm.deck.remaining) == 35 - 4
