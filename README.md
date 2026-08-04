# 7½ Men

Keeper dashboard for the 7½ Men league (Sleeper `1388606375239643136`). Its own
Streamlit app — it shares a look and a couple of league-independent utilities
with the Kreeper and Babies & Boomer tools, but the ruleset diverges far enough
that the engine is written from scratch.

```bash
.venv/bin/streamlit run app.py
```

Or via the preview server named `halfmen` (port 8537).

## The ruleset, as the engine encodes it

**Keepers** — five: three regular, two rookie. No position caps.

| Year held | What it costs |
|---|---|
| 1 | the round you drafted him, or his current ADP round — whichever is cheaper |
| 2 | your draft round minus three, or ADP — whichever is cheaper |
| 3 | ADP, no choice |
| 4 | the wall, unless you franchise him |

"Cheaper" always means the **later** round. Round 1 is the most expensive pick on
the board.

**The rookie-draft premium** — a player who entered through the rookie draft has
no veteran draft round to price against, so `R5` stands in for one. Year one is
**flat**: no ADP option, no cheaper-of. From year two the normal ladder resumes
with it as the anchor (5 → 2 → ADP → wall). It fires on three paths — kept
straight into a regular slot, promoted off taxi into one, or converted from a
rookie-keeper slot — and *not* on a rookie who went back to the pool and was
redrafted (he has a real round again, clock reset) or on an undrafted waiver
pickup (last available round, no premium). The predicate is **provenance, not
age**: `history.has_rookie_draft_provenance`, never `years_exp == 0`, because a
two-year taxi stash is no longer a rookie by that field and still prices at R5.
`R5_ROOKIE_PREMIUM` in `engine.py`, tunable via
`rules.keepers.rookie_draft_premium_round`.

**Franchise tag** — one player, years four and five, price frozen at the most
*expensive* round you have ever paid for him. Gone after year five. It still
burns a keeper slot. Because the freeze is at your peak price, the tag is worth
the most on a late find whose market ran away from him, and worth exactly
nothing on a career first-rounder.

**Rookie keepers** — any NFL rookie you **drafted**, in either draft. Not a
waiver pickup. Costs your last picks (R14, then R13), no three-year clock, yours
for his career. Trade him and the status dies: for his new owner he becomes a
regular keeper with the clock back at year one, at his original veteran round —
or at the R5 premium if he came through the rookie draft, so a swap can't be used
to reprice him.

**Owning the pick** — a keeper has to land on a round you actually hold. If it is
gone he **bumps up** to the next-earliest round you own, which costs you a more
valuable pick. Two keepers can never share a round, and allocation runs
most-expensive-first so a stud never gets pushed off his own round by a
late-round flier. The price itself travels with the player on a trade: an R7
keeper is an R7 again for an owner who still has their R7.

**Taxi** — two slots, two-year clocks, that year's rookie draft only. Never
startable, free of the bench, promotion is permanent. **Promoting does not cost
the rookie-keeper designation** — in year one or year two. A taxi stint is still
holding him, so the chain the rookie-keeper rule turns on is unbroken; he keeps
the last-round price and the no-clock and simply starts costing a rookie keeper
slot instead of nothing. That makes a stash a free two-year option on a rookie
keeper rather than a gamble, and means a team can carry four cheap young players
at once (two on taxi, two kept) with every regular slot still free.
`taxi.promotion_keeps_rookie_status` in config flips to `second_year_only` if the
league ever wants an early promotion to forfeit it.

**The pot** — unspent FAAB comes due, every dollar of it. The first $200 goes to
the Chase-bracket winner and everything above the cap goes to the champion. The
cap decides who gets paid, not how much is collected.

**Two lotteries** — both drafts are ordered by drum, weighted on different
things:

- rookie drum → regular-season record, worst first
- veteran drum → final standing *including the Chase bracket*, worst first

so a Chase win costs you veteran balls and weeks 15–17 still decide something.
Ball weights are `24 / 21 / 18 / 15 / 10 / 7 / 3 / 2` — strictly decreasing, so
the worst team always outranks the 6-8 team, but the bottom three sit three
points apart rather than eight, which makes an extra loss in week 13 nearly
worthless. Three guardrails, in order:

1. **No sweep.** The rookie drum draws first; its winner is held out of first
   choice in the veteran drum *that same year*.
2. **No back-to-back, per drum.** Win *first choice* of a drum and you cannot
   win first choice of *that drum* next year. The two are tracked separately —
   take first of the rookie draft this year and you are still free to take first
   of the veteran draft next year, and second choice of the rookie drum stays
   open to you. Acquiring a pick by *trade* does not burn your eligibility.
3. **Champion at the floor**, whatever their record.

Each drum produces a **selection order**, not a draft slot: first choice takes
any spot on the board they want.

## Year one (2026)

No keepers — every clock starts at zero after this season. Two drafts: the
rookie draft (2 rounds) then the veteran draft, both drawn flat at random.

The veteran draft is **13 rounds in year one, not 14**. 14 active spots plus 2
taxi slots is 16; a 14-round vet draft plus 2 rookies fills all 16 exactly and
forces both rookies onto taxi. At 13 you get the choice.

Set in `config.yaml` as `drafts.veteran_rounds_first_season`.

## Layout

```
app.py                 seven pages: Home, Rules, Keepers, Taxi Bay, The Pot, Draft, Lottery
config.yaml            every rule the engine branches on
halfmen/
  config.py            typed-ish accessors over the YAML
  engine.py            keeper pricing, the wall, the franchise tag, the bump
  lottery.py           the two drums and their guardrails
  pot.py               FAAB burn-down and settlement
  taxi.py              the bay and the squeeze
  draftboard.py        pick ownership, the grid, draft capital
  history.py           draft history and the keeper ledger, season by season
  storage.py           submitted slips (JSON per season, atomic writes)
  adp_board.py         consensus ADP -> a round in an 8-team draft
  rulebook.py          the league rulebook, rendered on the Rules page
  theme.py             the Acid palette, the type, the Streamlit chrome overrides
  adp/, names.py       ADP scrapers, carried over from the kreeper tool
tests/                 113 tests
scripts/refresh_adp.py daily consensus refresh
```

## Notes

- Every Sleeper read is disk-cached with a stale fallback. urllib3 on this
  machine's LibreSSL intermittently hangs on the league endpoints, so a stale
  cache beats a dashboard that spins.
- Sleeper's own `is_keeper` flag has been unreliable across seasons in the
  sibling leagues, so keeper years are counted from our own submitted ledger
  (`storage.load`) rather than trusted from the API.
- The league is still configured as **dynasty** on Sleeper (`type: 2`), which is
  why `max_keepers` reads 1 and the draft shows 2 rounds. Switch it to keeper
  after the two 2026 drafts and set `max_keepers` to 5.

## Still open

- **Year 2 of the premium ladder.** The written spec gives it as
  `min(5 - 3, adp_round)`, but `min()` over round numbers picks the *earlier*
  (more expensive) round, which contradicts the same spec's "Y2 does take the
  cheaper-of option" and would make a bust cost R2 against an R12 market. Built
  as cheaper-of — the later round — consistent with every other year. Flip
  `rules.keepers.adp_discount` off if the literal reading was intended.
- The pot cap is $200 as configured; worth re-checking against the championship
  payout once that is set.

## The Rules page

`halfmen/rulebook.py` holds the rulebook as structured prose — eleven sections
from the shape of the roster through to what is still being argued about. Every
number in it (`$100`, `13 rounds`, `24/21/18/…`, the franchise years) is read
out of `config.yaml`, the same file the engine branches on, so the rulebook
cannot drift away from what the code actually does. Change a rule in config and
the page changes with it.

It is the reference document for the league — worked examples for the price
ladder, the bump, and both the right and wrong franchise pick, plus an
order-of-operations for the offseason.

## Type and colour

**Floodlight / Acid**, one dark ground. Big Shoulders Display — a condensed
industrial cut — does the display work: masthead, section heads, nav pills and
every large number. It is the face Impact was standing in for in the mockup,
which only fell back to Impact because the artifact CSP blocks font CDNs. Archivo
sets the body, IBM Plex Mono carries anything with digits in it.

Acid lime does all the accent work on a near-black ground; electric blue is the
second voice and marks things that are *special* rather than merely good —
franchise tags, champions, the year you are currently in.

There is deliberately **no light theme**. One ground tuned properly beats two
half-tuned ones. `theme.PALETTES` is still a dict and `inject()` still takes a
palette argument, so a light ground can be added later as one more entry without
touching a single component.

Contrast is tested, not eyeballed. Every foreground/background pair the app puts
text on is declared in `theme.TEXT_PAIRS` and asserted against WCAG AA in
`tests/test_theme.py`. A second test walks every `var(--token)` in the stylesheet
and fails if the palette does not define it — so a new ground cannot ship with a
hole in it.

`streamlit` is **pinned** in requirements. The chrome overrides target Streamlit
internals (`[data-baseweb="tab"]`, `label:has(input:checked)`) and would silently
render raw on a version that moves them.
