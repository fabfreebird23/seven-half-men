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


def test_the_decided_list_carries_the_reasoning_not_just_the_verdict():
    reasons = " ".join(d["detail"] for d in agenda.decided())
    assert "indifferent" in reasons, "why the flat cap was wrong is the part people forget"
    assert "$120" in reasons


def test_the_settled_money_matches_the_config():
    buy_in = config.buy_in()
    titles = " ".join(d["title"] for d in agenda.decided())
    assert "$%d" % int(buy_in) in titles
    split = config.payout_split()
    assert "%d / %d / %d" % tuple(int(split[k]) for k in ("first", "second", "third")) in titles
