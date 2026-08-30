"""What the league voted on: the questions, and now the answers.

Year one is nothing but rule questions, and the answers were living in a group
chat where they scroll away. This is the list, on the front page, with the real
options next to each one so a vote does not have to start by re-explaining the
choice.

An item is OPEN until it appears under `settled.votes` in config.yaml, at which
point the same item renders as a RESULT - same question, same options, but with
the tally frozen and the answer called. That is deliberately one list rather
than two: the reason an option lost is the most useful thing to still be able
to read in March, and it disappears the moment results get rewritten as a bare
line of prose. The rulebook carries the rule; this carries how the room got
there, and who was in it.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import config


def _cap_at(buy_in: float) -> int:
    """What the pot cap becomes at a given buy-in.

    The cap is the third-place prize, so it moves with the buy-in on its own -
    which is the whole reason it was written that way.
    """
    pool = buy_in * int(config.league()["teams"])
    return int(round(pool * config.payout_split()["third"] / 100.0))


def _all_items() -> List[Dict[str, Any]]:
    buy_in = config.buy_in() or 100
    return [
        {
            "id": "deadline",
            "title": "Trade deadline",
            "why": "There isn't one. In a league where picks and keeper rights are "
                   "tradeable, a team out of contention in week 12 has real assets to sell "
                   "and somebody chasing a bye has real reason to buy — which is healthy "
                   "right up until it decides a playoff seed for a team that isn't playing "
                   "for anything.",
            "options": [
                ("Week 10", "Earliest of the common choices. Kills late-season seed-buying "
                            "outright, at the cost of a lot of legitimate trading."),
                ("Week 12", "The usual answer. Two weeks of the regular season left, so a "
                            "deal still has to be made by someone who is in it."),
                ("Week 13", "One week before the playoffs. Maximum trading, maximum risk of "
                            "a fire sale deciding the last bracket spot."),
                ("None", "Dynasty convention. Defensible here — the Chase and the two "
                         "lotteries mean nobody is truly playing for nothing in week 13."),
            ],
            "note": "Whatever you pick has to be set in Sleeper too — it enforces this one.",
        },
        {
            "id": "vetoes",
            "title": "Trade vetoes",
            "why": "Also unwritten. The question is not really “was that a fair trade”, "
                   "it is who gets to decide — and every league that lets the room vote "
                   "discovers that people veto trades that make an opponent better.",
            "options": [
                ("No vetoes, commissioner reverses collusion only",
                 "The modern default. Bad trades stand; a trade between two accounts run by "
                 "the same person does not."),
                ("League vote, 5 of 8 within 24 hours",
                 "The traditional answer. Slow, and in practice it punishes creative trades "
                 "more than crooked ones."),
                ("Commissioner review on every trade",
                 "Fastest, and it puts one person in the position of ruling on deals they "
                 "are competing against."),
            ],
            "note": "Worth deciding before the first trade, not during it.",
        },
        {
            "id": "waivers",
            "title": "Waiver tiebreaker",
            "why": "Two managers bid the same FAAB on the same player. Sleeper does not "
                   "offer a menu here — it breaks the tie on <b>rolling waiver priority</b>, "
                   "seeded by draft order (whoever picks LAST has the best priority), and a "
                   "team drops to the back of the line whenever it wins a claim. Free-agent "
                   "adds do not move you. So the real vote is whether to leave it alone or "
                   "have the commissioner reseed it.",
            "options": [
                ("Leave Sleeper's rolling order alone",
                 "Self-correcting over a season, and it quietly compensates whoever drew the "
                 "back of the draft — which fits a league that already runs the board off a "
                 "lottery."),
                ("Commissioner reseeds to reverse standings weekly",
                 "Helps the teams who need it most, every week. It is manual work someone "
                 "has to actually do, every week, all season."),
                ("Reseed once at the midpoint",
                 "Half the benefit, a fraction of the admin."),
            ],
            "note": "Sleeper seeds priority off the draft, so the lottery already decides "
                    "who starts at the front of the waiver line.",
        },
        {
            "id": "escalation",
            "title": "Does the buy-in escalate?",
            "why": "$%d is settled for 2026. Whether it climbs after that is not — and "
                   "because the pot cap is now the third-place prize, raising the buy-in "
                   "raises the consolation ceiling with it, automatically." % int(buy_in),
            "options": [
                ("Flat $%d forever" % int(buy_in),
                 "Pot cap stays $%d. Nothing to remember." % _cap_at(buy_in)),
                ("+$10 a year",
                 "2027 $%d, 2028 $%d, 2029 $%d. The cap rises $%d a year with it."
                 % (buy_in + 10, buy_in + 20, buy_in + 30, _cap_at(buy_in + 10) - _cap_at(buy_in))),
                ("+$20 a year",
                 "2027 $%d, 2028 $%d, 2029 $%d. The cap rises $%d a year — by 2029 the "
                 "consolation prize is $%d."
                 % (buy_in + 20, buy_in + 40, buy_in + 60,
                    _cap_at(buy_in + 20) - _cap_at(buy_in), _cap_at(buy_in + 60))),
            ],
            "note": "An escalator is a commitment device — it is easy to agree to in year "
                    "one and awkward to walk back in year four when somebody's circumstances "
                    "have changed. Worth saying out loud whether it can be voted down later.",
        },
    ]


def _settled() -> Dict[str, Any]:
    return dict((config.raw().get("settled") or {}).get("votes") or {})


def open_items() -> List[Dict[str, Any]]:
    """Still to vote on. Empty once everything is called."""
    done = _settled()
    return [it for it in _all_items() if it["id"] not in done]


def closed_items() -> List[Dict[str, Any]]:
    """Called votes, each carrying the answer and why it landed there.

    The stored ballots are left in place rather than cleared, so the tally on
    the page is the real one and stays auditable - including the fact that it
    was seven of eight.
    """
    done = _settled()
    out = []
    for it in _all_items():
        got = done.get(it["id"])
        if not got:
            continue
        it = dict(it)
        it["answer"] = got.get("answer") or ""
        it["tally"] = got.get("tally") or ""
        it["verdict"] = " ".join(str(got.get("note") or "").split())
        # Which option won, so the row can be marked rather than described.
        it["won"] = next((i for i, (lab, _d) in enumerate(it["options"])
                          if lab.strip().lower() == it["answer"].strip().lower()), None)
        out.append(it)
    return out


def turnout() -> str:
    return str((config.raw().get("settled") or {}).get("turnout") or "")


def settled_on() -> str:
    return str((config.raw().get("settled") or {}).get("date") or "")


PROPOSAL_URL = "https://claude.ai/code/artifact/308a42ba-a76e-4c8d-863a-f2d9b7acdd92"


def proposals() -> Dict[str, Any]:
    """Next season's proposal, written to be SPOKEN rather than read.

    Not a poll and not a summary. Each change carries the one line that lands
    it and the objection that will come back, because the objection is where
    these conversations actually go - and having the answer ready is the whole
    difference between a proposal and an argument.
    """
    return {
        "title": "One draft, one drum",
        "note": "Proposed for 2027. Nothing here changes anything about today\u2019s draft.",
        "url": PROPOSAL_URL,
        "items": [
            {
                "title": "One draft, 16 rounds",
                "say": "Two drafts, two lotteries and two sets of guardrails, for one "
                       "league. Next year it is one board, all players, sixteen rounds. "
                       "<b>Nobody has to draft a rookie</b> \u2014 and that is the point, "
                       "because taking one in the 6th finally costs you a veteran in the 6th.",
                "back": ("Doesn\u2019t that kill the rookie draft?",
                         "It kills the separate event, not rookie picks. Right now two "
                         "rookies are free because they come off a board that costs no "
                         "veteran capital. On one board they cost a real pick, which is how "
                         "a rookie stops being an entitlement and starts being a decision."),
            },
            {
                "title": "A kept rookie costs the round you took him in",
                "say": "This is the <b>normal</b> keeper path only. R5 exists because a "
                       "rookie-draft pick had no round to point at \u2014 give him a real "
                       "round and we use it. Take a rookie in the 12th and he keeps at R12, "
                       "not R5. Rookie-designated keepers are untouched.",
                "back": ("Does this change rookie keeper slots?",
                         "No. Two slots, your last rounds, no clock \u2014 all unchanged. "
                         "And the guys we just drafted still enter at R5 on the normal path: "
                         "a legacy rule covering sixteen players, then it retires itself."),
            },
            {
                "title": "Winning the Chase costs you lottery balls",
                "say": "Right now weeks 15 to 17 are a lap of honour. Under this, winning "
                       "the Chase costs you <b>9.4 points</b> of first choice and pays you "
                       "up to <b>$120</b>. That is a decision.",
                "back": ("So you want us to tank the Chase?",
                         "I want it to be a choice. Money now, or balls in the drum. Right "
                         "now there is nothing to choose between."),
            },
        ],
    }
