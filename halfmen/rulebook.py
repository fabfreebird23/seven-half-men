"""The rulebook, as prose.

Kept as data rather than baked into app.py so the league has one file to argue
with. Every number that also drives the engine is pulled from config, so the
rulebook cannot drift from what the code actually does.

Each section is (anchor, title, standfirst, [blocks]). A block is one of:
    ("p",     text)
    ("list",  [item, ...])
    ("table", [headers], [[cells], ...])
    ("note",  text)          - a dashed callout
    ("worked", title, [(label, value, detail), ...])   - a worked example
"""
from __future__ import annotations

from typing import List, Tuple

from . import config


def _n(path, default=None):
    cur = config.load()
    for k in path.split("."):
        cur = (cur or {}).get(k, {})
    return cur if cur not in ({}, None) else default


def _prem() -> int:
    return int(config.keeper_rules().get("rookie_draft_premium_round", 5))


def _ord(n: int) -> str:
    return "%d%s" % (n, {1: "st", 2: "nd", 3: "rd"}.get(n % 10 if n % 100 not in (11, 12, 13) else 0, "th"))


def sections() -> List[tuple]:
    kr = config.keeper_rules()
    fr = config.franchise_rules()
    tr = config.taxi_rules()
    ab = config.faab_rules()
    lr = config.lottery_rules()
    lg = config.league()
    rs = config.roster()
    vet = int(config.drafts()["veteran_rounds"])
    vet1 = config.veteran_rounds()
    rook = config.rookie_rounds()
    last = vet
    total = int(kr["total"])

    return [

("shape", "The shape of it", "Eight teams, PPR, and a keeper system with three extra layers.", [
 ("table", ["", ""], [
   ["Teams", "%d" % lg["teams"]],
   ["Scoring", "PPR"],
   ["Starters", " · ".join(rs["starters"]) + "  (%d)" % len(rs["starters"])],
   ["Bench", str(rs["bench"])],
   ["IR", str(rs["ir"])],
   ["Taxi", "%d" % int(tr["slots"])],
   ["Waivers", "FAAB, $%d for the season" % int(ab["budget"])],
   ["Playoffs", "%d teams, from week %d" % (lg["playoff_teams"], lg["playoff_week_start"])],
   ["Chase bracket", "the other four, weeks %s" % ", ".join(str(w) for w in lg["chase_weeks"])],
 ]),
 ("p", "Your active roster is <b>%d</b> — %d starters and %d bench — plus one IR slot and "
       "%d taxi slots that sit outside it." % (
        config.active_roster_size(), len(rs["starters"]), rs["bench"], int(tr["slots"]))),
]),

("year-one", "Season one is different", "Nobody has held anyone yet, so 2026 runs on its own rules.", [
 ("list", [
   "<b>No keepers.</b> Everyone starts empty. Every clock starts at zero <em>after</em> this season.",
   "<b>Two drafts, same as every year.</b> The rookie draft (%d rounds) runs first, then the "
   "veteran draft." % rook,
   "<b>The veteran draft is %d rounds this year, not %d.</b> See the note below — it is the one "
   "deliberate year-one change." % (vet1, vet),
   "<b>Both orders are drawn flat at random.</b> There are no standings to weight a drum with. "
   "The draw is seeded and reproducible so it can be run in front of everyone.",
   "<b>Taxi squads are live from day one.</b> You can stash rookies you take in the rookie draft, "
   "and their two-year clocks start now.",
   "<b>No pot.</b> It needs a full season of FAAB data to settle against, so nothing is billed "
   "until the %d offseason. The burn-down still tracks all season." % (int(lg["season"]) + 1),
 ]),
 ("note", "<b>Why %d rounds and not %d.</b> Your active roster is %d and taxi holds %d, so the "
          "roster tops out at %d players. A %d-round veteran draft plus %d rookie picks is exactly "
          "%d — which would <em>force</em> both rookies onto taxi and take the decision away from "
          "you. At %d rounds you land on %d and get to choose: promote one rookie and stash one, "
          "or stash both and carry an open bench spot." % (
            vet1, vet, config.active_roster_size(), int(tr["slots"]),
            config.active_roster_size() + int(tr["slots"]), vet, rook, vet + rook,
            vet1, vet1 + rook)),
]),

("keepers", "Keepers", "Five a year: three regular, two rookie. Keeping a player costs you the "
                       "draft pick in the round assigned to him.", [
 ("p", "At the end of each season you keep <b>%d</b> players. Everyone else goes back into the "
       "pool for next year's veteran draft. Keep a player at a 3rd and you give up your "
       "3rd-round pick that year." % total),
 ("p", "The price climbs the longer you hold someone, and after three years he is gone unless "
       "you franchise him."),
 ("table", ["Year you've held him", "What he costs"], [
   ["1st year", "the round you drafted him — or his current ADP round, whichever is <b>cheaper</b>"],
   ["2nd year", "your draft round minus %d — or ADP, whichever is <b>cheaper</b>" % int(kr["year2_bump"])],
   ["3rd year", "ADP. No choice."],
   ["4th year", "gone, unless you franchise him"],
 ]),
 ("note", "<b>Cheaper always means the later round.</b> Round 1 is the most expensive pick on the "
          "board and round %d the least. A 12th-rounder is cheap; a 2nd-rounder is not." % vet),
 ("p", "ADP is average draft position — where the fantasy world says he would go in a normal "
       "draft. It is the market price, and the dashboard pulls a daily consensus of it."),
 ("worked", "What that looks like on a late-round hit", [
   ("You draft him", "R12", "round 12 of the veteran draft"),
   ("Year 1", "R12", "his draft round beats his ADP, so you pay R12"),
   ("Year 2", "R9", "12 minus 3 — and by now the market has him at R3, so R9 is the cheaper of the two"),
   ("Year 3", "R3", "ADP only. No choice, no discount."),
   ("Year 4", "gone", "unless he is your franchise player"),
   ("Banked", "+15 rounds", "over the full three-year run"),
 ]),
 ("note", "<b>Year three never makes you money.</b> It prices at the market by definition, so the "
          "surplus is always exactly zero. Every round of profit you will ever make out of a "
          "keeper comes from years one and two. That is worth knowing before you spend a slot."),
 ("p", "There are <b>no position caps</b>. Five quarterbacks is legal, if that is the hand you "
       "want to play."),
]),

("premium", "What a rookie-draft pick costs to keep", "He never had a veteran draft round, so "
                                                     "there is nothing to price him against. R%d "
                                                     "stands in for one." % _prem(), [
 ("p", "Everything above prices a keeper off the round you drafted him in. A player who came into "
       "the league through the <b>rookie draft</b> has no such round — so his first regular-keeper "
       "year is a flat <b>R%d</b>. No ADP option, no cheaper-of choice, no discount for having "
       "taken him at 2.08 instead of 1.01." % _prem()),
 ("table", ["How he got here", "Year 1 regular-keeper cost"], [
   ["Rookie-draft pick, kept straight into a regular slot", "<b>R%d</b>" % _prem()],
   ["Rookie-draft pick, promoted off taxi into a regular slot", "<b>R%d</b>" % _prem()],
   ["Rookie keeper moved into a regular slot (one-way)", "<b>R%d</b>" % _prem()],
   ["Rookie-draft pick who went back to the pool and was redrafted",
    "his real veteran round — the clock reset, he is an ordinary pick again"],
   ["Undrafted, picked up on waivers", "your last available round. No premium, no provenance."],
 ]),
 ("note", "<b>R%d is a property of the holding stretch, not of the player.</b> Let him go back "
          "into the pool and whoever takes him in the veteran draft has an ordinary keeper at an "
          "ordinary round. That is also true if you are the one who redrafts him." % _prem()),
 ("worked", "The ladder, once the premium is the anchor", [
   ("Year 1", "R%d" % _prem(), "flat. The market is not consulted."),
   ("Year 2", "R%d" % max(1, _prem() - 3), "%d minus 3 — and the cheaper-of option is back on, so "
                                           "if the market has him later than R%d you pay that "
                                           "instead" % (_prem(), max(1, _prem() - 3))),
   ("Year 3", "ADP", "the market, no choice, same as anybody else"),
   ("Year 4", "the wall", "franchise slot only"),
 ]),
 ("note", "<b>Year one is the only flat year.</b> From year two the ordinary ladder resumes and "
          "the cheaper-of option comes back — which matters, because a rookie-draft pick who has "
          "not worked out is an R%d in year two and you will want the market price instead."
          % max(1, _prem() - 3)),
 ("p", "The premium still has to land on a pick you own. If your %s is gone it snaps <b>up</b> to "
       "the nearest earlier round you hold — a 4th, a 3rd, whatever exists. Never down." % _ord(_prem())),
 ("note", "Taxi time does not advance the clock. A player stashed two years and then promoted is "
          "in <b>year one</b> at R%d, not year three. The clock starts when he joins the active "
          "roster." % _prem()),
]),

("owning", "You have to own the pick", "A keeper lands on a round you actually hold.", [
 ("p", "If the round his price lands on has been traded away, he does not disappear — he "
       "<b>bumps up</b> to the next-earliest round you still own. That costs you a more valuable "
       "pick, which is the point: trading picks away has a price."),
 ("worked", "Bumping", [
   ("His price", "R7", "year one at the round you drafted him"),
   ("Your R7", "traded", "it went out in a deal in October"),
   ("What he costs", "R6", "the next-earliest round you still hold"),
 ]),
 ("list", [
   "Two keepers can never share a round. If both land on R9 the second one bumps to R8.",
   "Allocation runs most-expensive-first, so a stud is never pushed off his own round by a "
   "late-round flier — the cheap keeper is the one that moves.",
   "If you have traded so much that there is nothing left to land on, he is not keepable.",
 ]),
 ("note", "<b>The price travels with the player on a trade.</b> An R7 keeper stays an R7 keeper "
          "for whoever acquires him — the bump is worked out fresh for the new owner against the "
          "picks <em>they</em> hold. So a keeper is quietly worth more to a team that still owns "
          "his cost round, which is a real thing to price into a deal."),
]),

("rookies", "Rookie keepers", "Two of your five slots are reserved for rookies you drafted "
                              "yourself. They are the best assets in the league.", [
 ("list", [
   "They cost your <b>last picks</b> — R%d, then R%d. Effectively free." % (last, last - 1),
   "<b>No three-year clock.</b> You keep them for their whole career.",
   "You must have <b>drafted</b> him in his actual NFL rookie season and held him the entire "
   "time. Trade him and the status is gone forever.",
 ]),
 ("p", "The rookie draft is %d rounds — %d picks. A fantasy-relevant NFL class is closer to "
       "thirty, so every year a dozen-plus real rookies reach the veteran draft or the waiver "
       "wire. The rule has to say what happens to them, and it does: <b>any NFL rookie you "
       "drafted, in either draft. Not a waiver pickup.</b>" % (rook, rook * int(lg["teams"]))),
 ("table", ["How you got him", "Rookie keeper?"], [
   ["Taken in the rookie draft", "<b>Yes</b> — the obvious case"],
   ["Taken in the veteran draft, still an NFL rookie",
    "<b>Yes</b> — 16 rookie picks cannot cover a class, so this is not an accident of timing"],
   ["Won on waivers or FAAB in his rookie year",
    "<b>No</b> — a normal keeper on the three-year clock"],
   ["Traded to you", "<b>No</b> — the status dies on a trade, for both of you"],
   ["Drafted by you, stashed on taxi, then promoted",
    "<b>Yes</b> — a taxi stint is still holding him, so the chain is unbroken"],
 ]),
 ("note", "This does not dilute rookie picks the way it looks like it might. You only get "
          "<b>%d</b> rookie-keeper slots either way, so the binding constraint is the slots, not "
          "the entry route. What a rookie pick actually buys you is <em>first crack at the "
          "class</em>." % int(kr["rookie"])),
 ("p", "A rookie keeper you trade away becomes a <b>regular keeper</b> for his new owner, priced "
       "at the round he was originally drafted in, with the three-year clock starting over at "
       "year one."),
]),

("franchise", "The franchise slot", "One player per team can survive the three-year wall.", [
 ("list", [
   "Extends him <b>two more years</b> — year %d and year %d." % tuple(_fr_years()),
   "The price is <b>frozen at the highest you have ever paid for him</b>. If he keeps getting "
   "better you are not paying market.",
   "Year %d he is gone. No exceptions." % int(fr["final_year"]),
   "It still uses one of your %d keeper slots. You are buying years, not roster space." % total,
   "Locked in when you submit keepers. It cannot be moved later.",
 ]),
 ("note", "<b>&ldquo;Highest you have ever paid&rdquo; means the earliest round.</b> Which makes "
          "the tag counterintuitive: it is worth the most on a player whose market ran away from "
          "a cheap peak price, and worth <em>nothing</em> on a player who was always a "
          "first-rounder."),
 ("worked", "The right franchise pick", [
   ("Peak price paid", "R5", "his year-three price, back when the market had him at R5"),
   ("Market now", "R1", "he broke out after that"),
   ("Franchise price", "R5", "frozen"),
   ("Banked", "+4 rounds a year", "for two more years"),
 ]),
 ("worked", "The wrong one", [
   ("Peak price paid", "R1", "he has been a first-rounder the whole time"),
   ("Market now", "R1", "still is"),
   ("Franchise price", "R1", "frozen at nothing useful"),
   ("Banked", "+0", "you bought two years at full retail"),
 ]),
 ("p", "One slot. If two of your players hit year four in the same offseason, you pick one and "
       "the other goes back into the veteran draft pool — where anybody, including you, can "
       "draft him again at market price with a fresh clock."),
]),

("taxi", "The taxi squad", "%d slots. A place to park rookies you believe in but cannot use yet."
                           % int(tr["slots"]), [
 ("list", [
   "Rookies from <b>that year's rookie draft only</b>.",
   "<b>You cannot start them. Ever.</b> Not for a bye, not for an injury.",
   "They do not count against your bench and they carry over free — no keeper slot used.",
   "You can hold a player up to <b>%d years</b>, but you only have %d slots. One player for two "
   "years or two players for one year each — not four players." % (int(tr["years"]), int(tr["slots"])),
   "<b>Promoting is permanent.</b> Once he is on the active roster he cannot go back.",
   "<b>Promoting does not cost him the rookie-keeper designation.</b> Bring him up in year one "
   "or year two and he is still a rookie keeper: last-round price, no three-year clock. He just "
   "stops being free and starts costing one of your %d rookie keeper slots." % int(kr["rookie"]),
   "No adding to taxi mid-season.",
   "You can trade taxi players. They stay on taxi for the new team <em>if</em> that team has a "
   "slot free.",
 ]),
 ("note", "<b>The squeeze.</b> Hold last year's stash a second season and this year's rookie "
          "picks have nowhere to land. Two slots, two-year clocks and %d rookie picks a year do "
          "not fit together comfortably, and that tension is the whole point of the thing." % rook),
 ("p", "Because taxi costs no keeper slot and a promoted player keeps his rookie designation, a "
       "taxi stint is a <b>free two-year option</b> on a rookie keeper. You are not risking the "
       "asset by stashing him — you are deferring the slot. The scarce thing is the slot, not the "
       "player."),
 ("worked", "What a full farm system looks like", [
   ("On taxi", "2", "costing you nothing at all — no keeper slot, no bench spot"),
   ("Rookie keepers", "%d" % int(kr["rookie"]), "at R%d and R%d, no clock, held for their careers"
    % (last, last - 1)),
   ("Total", "4", "cheap young players carried at once, against %d regular keeper slots still free"
    % int(kr["regular"])),
 ]),
]),

("faab", "FAAB and the pot", "$%d for the season. Whatever you do not spend, you owe." % int(ab["budget"]), [
 ("p", "The Chase bracket — the four teams that miss the playoffs, playing weeks %s — does two "
       "things. It weights next year's veteran lottery, and it plays for a cash pot." % (
        ", ".join(str(w) for w in lg["chase_weeks"]))),
 ("p", "The pot is funded by <b>unspent FAAB</b>. Check out in October and sit on $85 and you pay "
       "the most. Grind waivers all year and you pay nothing."),
 ("table", ["Where it goes", ""], [
   ["First $%d" % int(ab["pot_cap"]), "to whoever wins the Chase bracket"],
   ["Everything above that", "to the league champion, on top of the championship money"],
 ]),
 ("note", "<b>The cap is a ceiling, not a discount.</b> Every unspent dollar comes due either "
          "way. The cap only decides <em>who</em> gets paid, which is what keeps the consolation "
          "prize from ever rivalling the title."),
 ("p", "The point of all of it: there is no free ride for quitting in November. You either play "
       "or you pay."),
 ("p", "One more waiver rule, and it is about price rather than permission. <b>Anyone can claim "
       "anyone.</b> There is no lock-out on picking a player back up after you cut him — but "
       "dropping him does not wipe what he costs to keep."),
 ("table", ["How he reached the wire", "What he costs whoever claims him"], [
   ["Drafted in this league at some point, then dropped",
    "<b>the round he was drafted in</b>, with his clock where it left off"],
   ["Never drafted here at all", "your last available round — the only genuinely cheap route"],
 ]),
 ("note", "<b>You cannot launder a price by cutting him.</b> That was the whole point of the old "
          "twelve-month lock-out, and carrying the price does the same job without asking anyone "
          "to police a transaction log — which nobody was going to do, and which Sleeper will "
          "not do for us. It also matches how a keeper already behaves in a trade: the price is a "
          "property of the player's run in this league, not of who happens to hold him."),
 ("p", "Worth knowing before you drop someone in a bye week. A 2nd-rounder you cut for a streamer "
       "is a 2nd-round keeper for whoever grabs him, and he is off your slip either way."),
]),

("lotteries", "The two lotteries", "Both drafts are ordered by drum, and the drums are weighted "
                                   "on different things on purpose.", [
 ("table", ["Drum", "Weighted by"], [
   ["Rookie draft", "regular-season record, worst team gets the most balls"],
   ["Veteran draft", "<b>final standing including the Chase bracket</b>"],
 ]),
 ("p", "That difference is deliberate. If both drums ran on regular-season record, weeks %s "
       "would stop mattering for anything but money and the four teams playing them would have a "
       "live reason to lose. Weighting the veteran drum on where you actually finished means a "
       "Chase win costs you veteran balls — which is exactly the trade the bracket is supposed "
       "to offer." % ", ".join(str(w) for w in lg["chase_weeks"])),
 ("p", "Ball weights, worst to best: <b>%s</b>." % " / ".join(
        "%d%%" % w for w in config.lottery_weights())),
 ("note", "The bottom three sit three points apart rather than eight. The worst team still has "
          "the best odds — strictly — but an extra loss in week 13 is worth about three "
          "percentage points, which is not enough to be worth engineering. That is the whole "
          "design goal: missing the playoffs should pay, being <em>worse</em> than that should not."),
 ("p", "<b>Each drum sets a selection order, not a draft slot.</b> Whoever wins first choice "
       "takes any spot on the board they want, second choice takes any that is left, and so on. "
       "Nobody is ever stuck picking from the 1 spot."),
 ("worked", "How the lock-out plays out over two years", [
   ("2027 rookie drum", "you win", "first choice. You take 1.01 and land the best rookie on the board."),
   ("2028 rookie drum", "barred", "from first choice only. You can still win <em>second</em> choice."),
   ("2028 veteran drum", "wide open", "winning the rookie drum last year has nothing to do with "
                                      "this one. Take first choice here if the balls fall your way."),
 ]),
 ("worked", "The guardrails, in the order they apply", [
   ("No sweep", "1st", "The rookie drum draws first. Its winner is held out of first choice in "
                       "the veteran drum — they can still land second."),
   ("No back-to-back", "2nd", "Win <b>first choice</b> of a drum and you cannot win first choice "
                              "of <b>that same drum</b> next year. The two drums are tracked "
                              "separately — take first of the rookie draft this year and you are "
                              "still free to take first of the veteran draft next year, and you "
                              "can still win second choice of the rookie drum. Acquiring a pick "
                              "by trade does not burn your eligibility; only winning it does."),
   ("Champion at the floor", "3rd", "Whoever wins the title takes the smallest ball weight in "
                                    "both drums, whatever their record was."),
 ]),
]),

("calendar", "The offseason, in order", "What happens when.", [
 ("worked", "Order of operations", [
   ("Weeks %s" % "-".join(str(w) for w in (lg["chase_weeks"][0], lg["chase_weeks"][-1])),
    "Chase bracket", "The four non-playoff teams play for the pot and for veteran lottery position."),
   ("Right after", "FAAB settles",
    "Unspent budget is totted up and billed. Chase winner takes the first $%d, champion takes the "
    "rest." % int(ab["pot_cap"])),
   ("Then", "Keeper slips",
    "Everyone submits %d: %d regular, %d rookie, franchise tag included if you are using it. "
    "The franchise choice is final at submission." % (
        total, int(kr["regular"]), int(kr["rookie"]))),
   ("Then", "The drums",
    "Both lotteries run after slips lock, so everyone knows what picks are actually live before "
    "the balls come out."),
   ("Then", "Rookie draft", "%d rounds, %d picks." % (rook, rook * int(lg["teams"]))),
   ("Last", "Veteran draft", "%d rounds, snake, minus every pick a keeper ate." % vet),
 ]),
]),

("open", "Still being argued about", "Two things the rulebook does not settle yet.", [
 ("list", [
   "<b>The pot cap is $%d</b> as configured. It should be set against the championship payout, "
   "and that has not been fixed yet. If the title pays less than $%d this is the wrong number."
   % (int(ab["pot_cap"]), int(ab["pot_cap"])),
   "<b>Year two of the R%d ladder.</b> The written spec gives it as <code>min(5 - 3, adp)</code>, "
   "but taken literally over round numbers that picks the <em>earlier</em>, more expensive round "
   "— which would make a rookie-draft bust cost R%d against an R12 market. It is built as "
   "cheaper-of, the later round, consistent with every other year. Worth confirming." % (
     _prem(), max(1, _prem() - 3)),
   "<b>Nothing has been exercised against real data.</b> Every rule above is unit-tested, but "
   "2026 is the first season and the first keeper slip is a year away. Expect at least one thing "
   "here to read differently once it has actually happened to somebody.",
 ]),
]),
    ]


def _fr_years():
    start = int(config.keeper_rules()["max_years"]) + 1
    extra = int(config.franchise_rules()["extra_years"])
    return (start, start + extra - 1)
