# Manager photos

`<sleeper_user_id>.jpg` — natural colour, square-ish, head and shoulders. This
is the circle that shows up next to a manager anywhere in the app (the
Around-the-League ladder, the rooting card, the tale of the tape, the bench
list). Until a file exists the manager gets his initials instead, so a missing
photo is never a broken image.

`<sleeper_user_id>_g.webp` and `_r.webp` — background-free cutouts with a
transparent background, used full-height on the matchup and Game-of-the-Week
covers: `_g` for the side being looked at, `_r` for the opponent. Without them
the cover falls back to that side's best projected starter's Sleeper headshot.

Ids are the Sleeper user ids in `config.yaml` under `managers:`.
