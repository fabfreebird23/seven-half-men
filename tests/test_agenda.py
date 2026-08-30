"""The open votes and the settled ones.

The numbers in here are read from config rather than typed, so the agenda cannot
quietly disagree with what the engine actually does - which is the exact failure
that would embarrass someone reading it out at a meeting.
"""
from __future__ import annotations

from halfmen import agenda, config, pot


def test_every_item_offers_real_options():
    for it in agenda._all_items():
        assert len(it["options"]) >= 2, "%s is not a choice" % it["title"]
        assert it["why"], it["title"]
        for label, note in it["options"]:
            assert label and note, "%s has a bare option" % it["title"]


def test_the_four_asked_for_are_there():
    ids = {it["id"] for it in agenda._all_items()}
    assert {"deadline", "vetoes", "waivers", "escalation"} <= ids


def test_every_item_is_either_open_or_closed_never_both():
    """The page renders open items as polls and closed ones as results. An
    item in both lists would be asked and answered on the same screen."""
    o = {i["id"] for i in agenda.open_items()}
    c = {i["id"] for i in agenda.closed_items()}
    assert not (o & c)
    assert (o | c) == {i["id"] for i in agenda._all_items()}


def test_a_called_vote_names_an_answer_that_was_actually_on_the_ballot():
    """A settled answer is matched back to its option by LABEL, so a typo in
    config.yaml would silently mark no option as the winner and the results
    block would render four losers and no result."""
    closed = agenda.closed_items()
    assert closed, "nothing has been called yet"
    for it in closed:
        assert it["answer"], it["id"]
        assert it["won"] is not None, (
            "%s: settled answer %r matches none of %r"
            % (it["id"], it["answer"], [l for l, _ in it["options"]]))
        assert it["tally"] and it["verdict"], it["id"]


def test_the_escalator_shows_what_it_does_to_the_pot_cap():
    """The cap is the third-place prize, so raising the buy-in raises the
    consolation ceiling automatically. Voting on one is voting on the other."""
    esc = next(i for i in agenda._all_items() if i["id"] == "escalation")
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


def test_the_2027_proposal_is_talking_points_not_a_poll():
    """It needs arguing about before it needs counting. Each change carries the
    line that lands it and the objection that comes back, because the objection
    is where the conversation actually goes."""
    p = agenda.proposals()
    assert len(p["items"]) == 3
    assert p["url"].startswith("https://")
    for it in p["items"]:
        assert it["say"], it["title"]
        q, a = it["back"]
        assert q.endswith("?"), "the pushback has to be an actual question: %r" % q
        assert a, "and it has to have an answer"
    flat = " ".join(it["title"] + it["say"] + " ".join(it["back"]) for it in p["items"])
    assert "16 rounds" in flat and "R5" in flat and "9.4" in flat
    assert "normal" in flat and "untouched" in flat, (
        "the R5 change is the NORMAL keeper path only - rookie-designated keepers "
        "cost your last rounds by design, and a veteran-draft rookie already "
        "qualifies for that today, so consolidation does not touch them")
    assert "still enter at R5" in flat, "the legacy rule has to survive being said out loud"


def test_no_talking_point_is_too_long_to_say():
    """If it cannot be read aloud in one breath it is a paragraph, not a line."""
    for it in agenda.proposals()["items"]:
        assert len(it["say"]) < 320, "%s is a speech: %d chars" % (it["title"], len(it["say"]))


def test_the_proposal_says_it_does_not_touch_todays_draft():
    """Somebody will read this on draft day and wonder if the rules just moved."""
    assert "draft" in agenda.proposals()["note"] and "Nothing here changes" in agenda.proposals()["note"]
