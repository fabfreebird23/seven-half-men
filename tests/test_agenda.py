"""The open votes and the settled ones.

The numbers in here are read from config rather than typed, so the agenda cannot
quietly disagree with what the engine actually does - which is the exact failure
that would embarrass someone reading it out at a meeting.
"""
from __future__ import annotations

from halfmen import agenda, config, pot


def test_every_item_offers_real_options():
    for it in agenda.open_items():
        assert len(it["options"]) >= 2, "%s is not a choice" % it["title"]
        assert it["why"], it["title"]
        for label, note in it["options"]:
            assert label and note, "%s has a bare option" % it["title"]


def test_the_four_asked_for_are_there():
    ids = {it["id"] for it in agenda.open_items()}
    assert {"deadline", "vetoes", "waivers", "escalation"} <= ids


def test_the_escalator_shows_what_it_does_to_the_pot_cap():
    """The cap is the third-place prize, so raising the buy-in raises the
    consolation ceiling automatically. Voting on one is voting on the other."""
    esc = next(i for i in agenda.open_items() if i["id"] == "escalation")
    labels = " ".join(l for l, _ in esc["options"])
    assert "+$10" in labels and "+$20" in labels
    body = " ".join(n for _, n in esc["options"])
    assert "$110" in body and "$120" in body


def test_cap_at_tracks_the_real_settlement():
    """If these ever disagree, the agenda is lying about the money."""
    assert agenda._cap_at(config.buy_in()) == pot.cap_amount()[0]

def test_settled_business_is_not_left_on_the_front_page():
    """Once voted, a decision belongs in the rulebook. Two places to look is one
    too many, and the front page should be what still needs doing."""
    assert not hasattr(agenda, "decided")


def test_the_rulebook_carries_the_settled_money():
    """Home is what still needs doing; the rulebook is where anyone looks in
    March. The money decisions have to be findable there, not only in a commit."""
    from halfmen import rulebook
    money = next(s for s in rulebook.sections() if s[0] == "money")
    flat = str(money)
    assert "$100" in flat and "$800" in flat, "buy-in and pool"
    assert "$480" in flat and "$200" in flat and "$120" in flat, "the three prizes"
    assert "third-place prize, not a fixed number" in flat
    assert "indifferent" in flat, "why the flat cap was wrong"
    for pct in ("60%", "20%", "10%"):
        assert pct in flat, "the overflow split"


def test_the_2027_proposal_is_on_the_front_page_but_is_not_a_vote():
    """It needs arguing about before it needs counting, and four live votes are
    already above it - a second block of eight would make both harder to read."""
    p = agenda.proposals()
    assert len(p["items"]) == 3
    assert p["url"].startswith("https://")
    flat = " ".join(t + b for t, b in p["items"])
    assert "16 rounds" in flat and "R5" in flat and "9.4" in flat
    assert "2026 rookie class still enters" in flat, "the legacy rule has to be explicit"


def test_the_proposal_says_it_does_not_touch_todays_draft():
    """Somebody will read this on draft day and wonder if the rules just moved."""
    assert "today's draft" in agenda.proposals()["note"]
