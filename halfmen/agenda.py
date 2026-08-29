"""What the league still has to vote on, and what has already been settled.

Year one is nothing but rule questions, and the answers were living in a group
chat where they scroll away. This is the list, on the front page, with the real
options next to each one so a vote does not have to start by re-explaining the
choice.

Only the OPEN ones live here. Once something is voted it belongs in the
rulebook, not on a running list of recent news - the rulebook is where anyone
looks in March when they have forgotten what was agreed, and two places to check
is one too many.
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


def open_items() -> List[Dict[str, Any]]:
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


PROPOSAL_URL = "https://claude.ai/code/artifact/308a42ba-a76e-4c8d-863a-f2d9b7acdd92"


def proposals() -> Dict[str, Any]:
    """What is being proposed for next season, in brief.

    Deliberately NOT polls yet. These need arguing about before they need
    counting, and four live votes are already sitting above them - a second
    block of eight would just make both harder to read. They become polls the
    day somebody calls the question.
    """
    return {
        "title": "One draft, one drum",
        "note": "Proposed for 2027. Nothing here changes anything about today's draft.",
        "url": PROPOSAL_URL,
        "items": [
            ("One draft, 16 rounds",
             "Rookies and veterans on the same board, one order, one lottery. Sixteen "
             "rounds is the 14 we draft now plus the 2 the rookie draft used, so nobody "
             "loses a pick."),
            ("A kept rookie costs the round you took him in",
             "R5 was only ever a stand-in for rookies who had no veteran round. Merge the "
             "drafts and every player has a real one. <b>The 2026 rookie class still enters "
             "at R5</b> &mdash; it is a legacy rule covering sixteen players, then it retires."),
            ("Winning the Chase costs you lottery balls",
             "One drum, seeded on regular-season record, with the Chase result re-sorting "
             "the four weights held by the teams that missed the playoffs. Winning it costs "
             "<b>9.4 points</b> of first choice and pays up to <b>$120</b> &mdash; which "
             "makes weeks 15 to 17 a decision instead of a lap of honour."),
        ],
    }
