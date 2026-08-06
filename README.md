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

**Dropping a player does not launder his keeper price.** No re-add lock-out —
anyone can claim him, a league mate or the manager who just cut him. A player
drafted in this league at any point keeps his draft round as the *anchor* and his
clock where it left off, and the normal ladder runs from there (so year one is
still the cheaper of that round or his current ADP). Only a player never drafted
here — undrafted in the veteran draft, then picked up — prices off your last
available round, which is the one genuinely cheap route onto a roster.

This replaced a twelve-month lock-out, and the reason it can is that **cutting
gains you nothing**: year one already offers the cheaper of the draft round and
current ADP, so a drop-and-reclaim lands on exactly the number keeping him would
have. The exploit the old rule guarded against stops existing once the price
follows the player. Same principle as a trade: the price belongs to the player's
run in the league, not to whoever holds him.

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

## The two draft boards

**Pre-Season → Draft → Rookie draft** is the one that runs first: 2 rounds, 16
picks, in whatever order the drum settled. `rookie_snake` in config decides
whether round two snakes back or repeats round one — the written rules only ever
said "2 rounds, 16 picks" and never settled it, so it is a flag rather than an
assumption.

No keeper ever strikes a pick off that board, because a keeper costs a *veteran*
round — which is why it is its own `draftboard.rookie_grid` rather than a flag on
`grid()`. The page leads with what a pick there is actually worth to hold: R13/R12
in a rookie keeper slot, R5 in a regular one, free on taxi, or nothing if you let
him go back to the pool. Only two of the sixteen can end up in rookie slots on any
one team, which is what makes the back half of the board a different decision from
the front.

## Running the season-one draw

**Pre-Season → Lottery.** The draw sits at the top of that section on every one
of its leaves, so any of the three gets you there.

The controls are **locked behind a password** so a stray click cannot re-draw or
rewind the real thing mid-ceremony. Everyone else can still watch: the board, the
hat and each envelope update for them as you open them — only the buttons are
gated. Unlock persists for your browser session.

The password lives in `config.yaml`. **This repo is public**, so treat it as a
speed bump rather than a secret; set `draw_password` in `.streamlit/secrets.toml`
(gitignored) and in the Streamlit Cloud secrets box to override it with something
that is not in git.

Pick a seed, hit **Draw both orders**. Then run the reveal: **Open next** opens
one envelope at a time, or flip **Auto** and set a pause to let it run hands-free.

Envelopes are read **back to front** — last pick first, first choice last — so
the room learns who is stuck at the back while the prize is still in the hat.
Unopened slots stay visible as `?` rather than appearing as they are drawn,
because the empty space above is the tension. Names still in the hat show as
chips and disappear as they come out. The last envelope of each act gets the
loud treatment, since first choice is the only one anybody will remember.

Both drafts run as two acts: the whole rookie order, then the whole veteran
order. Reveal progress is stored with the draw, not in the session, so a manager
watching on their phone sees the same envelope open at the same moment as the
room. **Reset the reveal** puts them all back without re-drawing. It writes to `data/keepers_2026.json`, not
to session state, so every manager sees the same order and it survives a refresh
— it used to live in `st.session_state`, which meant the commissioner saw the
result and everyone else saw "nothing drawn yet". The board and the draft-capital
strip both read the saved order.

The seed is the point: anyone can re-enter it and get the identical order back,
so the draw is reproducible rather than something the league has to take on
trust. Both drafts come from one seed (veteran uses `seed + 1`, so the two orders
differ). Re-drawing overwrites.

Auto uses a blocking sleep, so the buttons will not respond mid-pause — if you
want to talk over it, use **Open next**.

`data/keepers_*.json` is gitignored: it is runtime league state, not source, and
a stray local click should never land in a commit looking like the real record.

One caveat: `data/` is ephemeral on Streamlit Cloud, so a container restart can
lose the file. **Screenshot the result, or note the seed** — the seed alone is
enough to regenerate it exactly.

## Year one (2026)

No keepers — every clock starts at zero after this season. Two drafts: the
rookie draft (2 rounds) then the veteran draft, both drawn flat at random.

The veteran draft is **13 rounds in year one, not 14**. 14 active spots plus 2
taxi slots is 16; a 14-round vet draft plus 2 rookies fills all 16 exactly and
forces both rookies onto taxi. At 13 you get the choice.

Set in `config.yaml` as `drafts.veteran_rounds_first_season`.

## Layout

```
app.py                 four sections, sixteen leaves, routed on ?p=&g=&t=
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
  valueboard.py        every roster priced for next year, plus the franchise tag
  theme.py             the Acid palette, the type, the Streamlit chrome overrides
  adp/, names.py       ADP scrapers, carried over from the kreeper tool
tests/                 218 tests
scripts/refresh_adp.py daily consensus refresh
```

## Navigation

Grouped by **season phase**, not content type, and routed entirely through
`?p=&g=&t=`. There is no tab row: the top bar is the wordmark and a phase status
line, and every route lives in a floating pill **bottom bar** whose sections open
a sheet listing **every leaf in that phase, one tap away**. The sheet used to
drill down — section, then group, then leaf — but that middle tap only ever
existed because the sheet could not hold everything, and it can. Groups are
headings now, not rows. The sheet scrolls when it outgrows a phone and opens
scrolled to wherever you already are, so the current page is always visible and
lit. Same pattern the Kreeper and Babies & Boomer apps converged on.

```
Home
Pre-Season   Keepers · Draft · Rookies & Taxi · Lottery
In-Season    The Wire · The Pot
Rules
```

Rules gets its own slot rather than folding under a phase — it is a twelve-section
reference document and year one is nothing but rule questions.

The bar is injected via `components.html` reaching `window.parent.document`,
because `st.markdown` strips `<script>` and the handlers have to be real. That is
the most version-fragile thing in the app, which is why `streamlit` is pinned.
`tests/test_routes.py` walks all twenty routes through Streamlit's own harness
and asserts each renders real content — most of them are dark in year one, so a
route that silently rendered nothing would not surface until the season started.

## Who sees what

Whose team the "your" views show comes from `?team=<sleeper_id>` in the URL,
falling back to `me` in config. Each manager can bookmark their own, and a link
pasted in the group chat opens on whatever the sender was looking at. The picker
sits beside the masthead.

## Home

The first block is **your team**, not the league's — one card rather than a strip
of tiles plus a loose table. It answers the two questions a manager actually
opens this for: where do I stand, and what is it costing me.

- A **band of two numbers**, never one. Two rather than one on purpose: a single
  figure leaves dead air beside it, and before the season starts a lone em-dash
  in an empty band reads as broken rather than as "not yet". In season it is
  record and standing; once the draw is run it is your rookie and veteran slots;
  before that it is the eight teams in the drum and your one-in-eight odds — a
  true pair, because season one is drawn flat. The band closes with a hairline
  season rule so progress frames the card instead of competing with the meters.
- **Three meters**, because all three are fractions of something — $100, five
  keeper slots, two taxi slots. The fraction is drawn rather than left to be
  worked out. An expiring taxi pod is coloured apart from a live one, so "2 of 2"
  and "2 of 2 with a decision due" cannot look identical.
- **The contracts in the footer**: best and worst value you hold, priced against
  the market, plus the taxi-squeeze warning when there actually is one.

It degrades rather than lies. An ineligible player — one at the three-year wall —
is never offered as your "best value", because it is not a contract you can take.
`$0` FAAB reads as owing the pot nothing rather than as an empty tank, since the
pot is funded by what you did *not* spend. The accent colour is reserved for a
placing worth having; eighth of eight is not lit up like a prize.

The card is deliberately *not* another row of liquid bowls. The league block
below already carries four, and eight identical circles stacked on a phone stop
reading as information.

> One trap worth knowing: `.rule` was already taken by the rulebook's section
> cards, which set their own padding. Reusing the name inside the card turned a
> 3px hairline into a 34px gap. The class is `.season` now.

## Where the data lives

Everything this app *writes* — keeper slips, the season-one draw, and any draft
picks entered by hand — is one JSON blob per season. It is written to two places
at once:

- `data/keepers_<season>.json` on disk, always.
- `data/keepers_<season>.json` on a **`league-data` branch of this repo**, when
  a token is configured.

The second one is the copy that matters on Streamlit Cloud, which deletes the
container's disk on every reboot and every redeploy. Without it, rebooting the
app mid-draw would blank the order in front of eight people. A *branch* rather
than `main` on purpose: a commit to `main` triggers a redeploy, which restarts
the container — the exact thing being guarded against.

To turn it on, put a fine-grained PAT with **Contents: read & write** on this
repo into the app's secrets (Streamlit Cloud → Settings → Secrets), and the same
in a gitignored `.streamlit/secrets.toml` for local work:

```toml
github_token = "github_pat_..."
github_repo = "fabfreebird23/seven-half-men"   # optional, this is the default
github_branch = "league-data"                  # optional, this is the default
```

The `league-data` branch already exists. Reads are cached for five seconds so
a room watching the draw sees each envelope open near-live without hammering the
API, and a read failure serves the last good value rather than an empty board.
Any push failure degrades to the local file instead of raising — a save is never
lost, only made fragile.

GitHub's own staleness is the thing to design around, and it was found by running
the real round trip against the real repo rather than a mock: the contents API is
served through a CDN that holds a copy for up to a minute, so **an overwrite read
back the previous value**. Reads carry a cache-busting parameter, but measurement
says that does not reliably beat it — so the real defence is that for ninety
seconds after a write this process trusts what it wrote over anything the API
hands back. On the night, the alternative is the commissioner opening an envelope
and the board rolling backwards in front of the room.

**Testing it**: Pre-Season → Draft → Enter results has a *Test the connection*
button behind the commissioner password. "Is my token set up right" is not
answerable by reading config — a token can be present and expired, present and
scoped to the wrong repository, or the secrets file can have failed to parse and
left nothing at all — so the button does the real thing and names the actual
failure. It deliberately does **not** require the read-back to be byte-fresh; a
stale-but-present body still proves the read path works, and a probe that failed
on CDN lag would cry wolf. Each run leaves a `connection check` commit on the
branch, which doubles as a record of when it was last known good. The commissioner surfaces say which mode they are in,
so nobody types in a draft that is about to evaporate.

The Sleeper cache under `data/` is *not* covered by this and does not need to be:
it rebuilds itself from the API.

## Notes

- Every Sleeper read is disk-cached with a stale fallback. urllib3 on this
  machine's LibreSSL intermittently hangs on the league endpoints, so a stale
  cache beats a dashboard that spins.
- Sleeper's own `is_keeper` flag has been unreliable across seasons in the
  sibling leagues, so keeper years are counted from our own submitted ledger
  (`storage.load`) rather than trusted from the API.
- **The masthead carries a six-character build fingerprint**, a hash of the
  injected stylesheet. Streamlit Cloud can re-run `app.py` while keeping an
  already-imported module in memory, so a deploy lands with the *old* CSS still
  being injected and nothing on the page says so — it has bitten all three of
  these dashboards. If the page looks wrong and the fingerprint has not moved,
  the process needs a **Reboot app** from the Cloud menu, not another commit.
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

The glance gauges are **bowls of liquid**, not rings. The whoop app this borrows
from runs a spring-damped surface sim per animation frame, but Streamlit does not
execute script tags inside markdown, so `theme.liquid()` does the same idea in
pure CSS: two travelling waves at different speeds and directions plus a slow
bob, with periods that do not divide into each other so the loop never visibly
repeats. The fill level rides a custom property rather than an inline transform,
because CSS animations beat inline styles and the bob keyframes would otherwise
flatten every bowl to the same height. It is clamped short of the brim on
purpose — a bowl filled to the top has no surface and reads as a solid disc.

Four bespoke visuals, each earning its place by saying something a table cannot:

- **Liquid bowls** (`theme.liquid`) for the glance metrics.
- **Year pips** (`theme.pips`) — the whole three-year clock, the wall, and the two
  franchise years beyond it, in about 90px.
- **The FAAB burn-down** (`theme.burndown`) — cumulative spend per team against
  the budget ceiling, with a dashed bracket from each highlighted endpoint up to
  that ceiling, because the gap *is* the bill. A flat line reads as quitting in a
  way "$89 owed" in a column never will.
- **The draft-capital strip** (`theme.capital_strip`) — one block per round, so
  you read *which* picks a team is missing rather than how many. A team without
  its 1st and 2nd is in a completely different position from one without its
  12th and 13th, and a count cannot say so.

Plus taxi pods with a per-year clock, since the squeeze is the league's most
confusing rule and prose was carrying all of it.

Most of that is dark in year one — pips and the burn-down need a season, the
board needs a draft. The bowls are the only one visible before week 1.

On a phone all seven tabs stay on one line: the two long labels shorten to
"Taxi" and "Pot" via `:nth-child` rather than the type squeezing to nothing.
That couples the stylesheet to `TABS` order in `app.py`, so a test asserts the
two stay in step — reorder the tabs without updating the CSS and it fails rather
than silently relabelling the wrong one.

Contrast is tested, not eyeballed. Every foreground/background pair the app puts
text on is declared in `theme.TEXT_PAIRS` and asserted against WCAG AA in
`tests/test_theme.py`. A second test walks every `var(--token)` in the stylesheet
and fails if the palette does not define it — so a new ground cannot ship with a
hole in it.

`streamlit` is **pinned** in requirements. The chrome overrides target Streamlit
internals (`[data-baseweb="tab"]`, `label:has(input:checked)`) and would silently
render raw on a version that moves them.
