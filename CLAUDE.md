# MTG Creature Type-Line Groups

Exploration of combinatorial groups of Magic: The Gathering creatures based on
shared creature subtypes, with a static web UI to browse results. Data comes
from the Scryfall API. Not a git repository.

## Base rules (apply to every group/dataset)

- Cards must be **Vintage-legal** (`legalities.vintage` is `legal` or `restricted`).
- **No double-faced cards** (layouts excluded: transform, modal_dfc, meld,
  reversible_card, battle — plus token/emblem/art_series/etc.). Flip and
  adventure cards are allowed but each face's type line is parsed separately.
- Subtypes are the words after the em dash (—) on a face whose left side
  includes "Creature", validated against Scryfall `/catalog/creature-types`
  (350 types). This handles the multi-word subtype "Time Lord" and drops
  Un-set joke type lines (e.g. B.F.M.).
- Within a group: **unique type lines**, **every pair of cards shares ≥1
  subtype**, and **no subtype is common to the whole group** (trivial
  all-share-one-type groups are deliberately excluded).

## Named query patterns

Patterns are specified by digit examples where each digit is a subtype and
each row is one creature's subtype set (matching is up to relabeling):

- **Pattern A**: exactly 4 creatures, ≥6 distinct subtypes that each appear
  on ≥2 of the cards. That needs ≥12 subtype slots, so it is enumerated
  exhaustively in two families: all four cards 3-subtype (forces every
  subtype on exactly 2 cards, every pair sharing exactly 1 — the Pasch/K4
  structure) and groups containing one of the rare 4+-subtype sets (anchored
  scan). 400 groups; near-dupes (3+ shared cards vs a kept group) dropped
  for the browser (326 kept), sorted by shared-subtype then union count desc.
- **Pattern B**: `123 / 124 / 345 / 15 / 25` — 5 creatures / 5 subtypes;
  exhaustively enumerated (247 groups).
- **Pasch**: `123 / 145 / 246 / 356` — 4 creatures / 6 subtypes, every subtype
  on exactly 2 cards, every pair sharing exactly 1; exhaustive. Exactly the
  all-3-subtype family of Pattern A — 234 of its current 400 groups, though
  the shipped `pasch-groups.json` still holds the 233 from the 2026-07-09
  build (see § Data vintage).
- **Pattern C (CMR Partners)**: Pattern A/B groups anchored on two Commander
  Legends partner cards — one matching `set:cmr o:partner c:w`, a different
  card matching `set:cmr o:partner` (anchor lists fetched from the Scryfall
  search API at runtime). The anchors are the commander pair: the remaining
  cards must fit within the union of the anchors' color identities, so the
  pool tracks one card per (subtype set, color identity). With two slots
  pinned, pattern A is enumerated exhaustively; pattern B is exhaustive and
  empty (no B group contains two partner subtype sets even before the
  identity filter). Under the ≥6-subtypes-shared-twice Pattern A definition
  the dataset is **still empty as of the 2026-08-11 build** (11 white / 43
  any anchor cards, 121 viable pairs, 0 completions) — partner anchors are
  too small to
  reach 12 subtype slots in any completable way, even ignoring the identity
  filter (under the older ≥6-distinct-subtypes rule it had 695 groups).
  Single-subtype partners (Angel, Horse, Golem…) can never anchor — their
  subtype would be common to the whole group.

Exact-structure searches use forced completion: choose the free sets, derive
the remaining sets from the structure, then look them up in the pool.

## Files

- `index.html` — self-contained browser UI (no dependencies). Shows Patterns
  A/B/C via combinable checkboxes synced to `?data=` (comma-separated subset
  of `a,b,c`; default all); groups are labeled `A12`/`B37`/`C5` with
  `#gaN`/`#gbN`/`#gcN` anchors. Supports
  comma-separated AND search terms, clickable subtype chips (add term), click
  card image (zoom lightbox with the card's Scryfall link; Esc/click closes),
  click card name — marked with a magnifying-glass icon — to filter to groups
  with that card,
  per-group favorites (localStorage, keyed by dataset + sorted card names)
  with a favorites-only filter, a per-group exclude list (same key, stored
  under `mtg-excluded-groups`) whose members are hidden from every view
  except the Exclude List toggle itself — the one place they can be put back,
  and which is mutually exclusive with the Favorites view — a Stats toggle
  (synced to `?stats=1`) showing per-pattern subtype instance counts, and an
  Export button downloading the currently shown groups as a text file. Every group gets a deck-building
  Scryfall link — `-is:digital -is:reprint` plus one `(t:x or t:y …)` clause
  per creature, i.e. cards sharing a subtype with every group member.
  A click that drops a group out of the current view (excluding it, or
  un-saving it while Favorites is on) runs `collapseOut` first: fade, then
  collapse the space, then re-render. That is why `main` spaces its children
  with margins rather than a grid `gap` — a gap outlives its row shrinking to
  0, so the space could never fully close.
  Each card slot has ▲/▼ arrows (greyed when the slot has no alternates) that
  cycle it through the other cards in `alternates.json` carrying the slot's
  subtype set — a group's structure depends only on the sets, so any of them
  fills the slot equally well and the type summary, chips, and Scryfall link
  are unchanged by a swap. Matching is by **superset**: an Elf Soldier slot
  also offers Citanul Stalwart (Elf Druid Soldier), which is still an Elf and
  still a Soldier. A widened card keeps the slot's `subtypes` and carries its
  surplus in `extra`, rendered as dashed dim chips — they never take a shared
  color, never reach the type summary, and never enter the Scryfall link,
  because the group does not rest on them; search does match them, so what is
  on screen stays findable. Swaps live in `SWAPS` (session-only, deliberately not
  persisted) keyed by `groupKey(e) + '#' + slot`; `shownCards(e)` resolves them
  and is what render, the filters, and Export read. `e.cards` is never mutated
  — `groupKey` is built from it, so favorites and exclusions survive a swap.
  Cycling back onto the group's own card clears the swap; while swapped, an
  `n/N ⟲` badge next to the name resets the slot. An arrow click rebuilds only
  that one `.card` via `buildCard` rather than calling `render()`, which would
  rebuild every group and could drop this one out from under the cursor when
  the incoming card no longer matches an active search term.
- `groups.json`, `pattern-a-groups.json`, `pattern-b-groups.json`,
  `pattern-c-groups.json`, `pasch-groups.json` — datasets: arrays of groups;
  each card has `name, type_line, subtypes, image, url`. The UI fetches only
  the Pattern A/B/C files; `groups.json` and `pasch-groups.json` are kept
  (and still deployed) but no longer browsable.
- `alternates.json` — `"Beast|Frog|Zombie"` (sorted subtypes, the same array
  the UI already holds per slot) → every Vintage-legal single-faced card whose
  subtypes **include** that set, as `name, type_line, image, url`, plus
  `extra` (sorted surplus subtypes) on the ones that carry more. Ordered
  exact-matches-first, then by how many surplus subtypes, then alphabetically.
  Scoped to the sets the shipped datasets use: 471 sets / 4,462 cards (920
  with surplus subtypes), 222 of them with more than one card. A missing file
  just leaves every arrow greyed.
- `creatures-3plus-subtypes.csv` — catalog of creatures with 3+ subtypes
  (NOTE: predates the Vintage/single-faced filters).
- `creature-groups.md` — markdown listing of the `groups.json` dataset.
- `scripts/` — generators (see below).

## Running

Serve the UI locally (required — the JSON fetch breaks over `file://`):

    ./local_server.sh        # http://localhost:8123 (port from .env)

## Deploying

Live at https://mtg.jefamirault.com/ (shared personal droplet; target in
`.env`, template in `.env.example`).

    ./deploy.sh --dry-run   # preview
    ./deploy.sh

Ships only `index.html` + the six dataset JSONs (allowlist in `deploy.sh`);
`scripts/`, docs, CSV, and `.env` never leave this machine. Content deploys
need no nginx reload. After regenerating a dataset, just deploy again.

Every deploy also ships a `deploy.json` stamp (UTC timestamp, short commit SHA, branch, dirty
flag). It is public on purpose and is what https://status.jefamirault.com/ reads to report what
is live here — see `~/devops/PATTERNS.md` § Deploy stamping.

## Workflows

Regenerating data needs the Scryfall bulk file. Fetch it and the creature
types catalog into `data/` (gitignored, ~200 MB) with:

    ./scripts/fetch_bulk.sh

Scryfall serves bulk data **only as gzipped JSONL** — the old plain-`.json`
array URL 404s — so the helper converts it to a JSON array, which is the
shape every generator expects (`json.load(open(BULK))`). It also writes
`data/SOURCE.txt` recording the download URI, Scryfall's `updated_at`, the
card count, and the catalog size; keep that, it is the only provenance for a
given build (Scryfall publishes no historical snapshots, so a build is not
reproducible after the fact). Send a `User-Agent` header on Scryfall API
requests — they 403 without one; prefer bulk data over paging
`/cards/search` for dataset work.

    python3 scripts/find_groups.py  data/oracle-cards.json data/creature-types.json creature-groups.md groups.json
    python3 scripts/pattern_a.py    data/oracle-cards.json data/creature-types.json pattern-a-groups.json
    python3 scripts/pattern_b.py    data/oracle-cards.json data/creature-types.json pattern-b-groups.json
    python3 scripts/pattern_c.py    data/oracle-cards.json data/creature-types.json pattern-c-groups.json
    python3 scripts/pasch.py        data/oracle-cards.json data/creature-types.json pasch-groups.json
    python3 scripts/catalog_subtypes.py data/oracle-cards.json data/creature-types.json creatures-3plus-subtypes.csv

`alternates.py` reads the pattern datasets to scope itself, so it runs **after**
them (and again whenever they are regenerated, or the UI's cycle arrows offer
cards from the older build):

    python3 scripts/alternates.py data/oracle-cards.json data/creature-types.json alternates.json pattern-a-groups.json pattern-b-groups.json pattern-c-groups.json

It asserts every card the datasets display is present in its own set's
alternates — that is the tripwire for the two files coming from different bulk
snapshots.

The bulk file carries **previewed but unreleased** sets; the Vintage-legal
base rule gates them out automatically (they are `not_legal` until release),
so a refresh picks up only sets that have actually gone legal.

All generators verify their structural constraints with assertions before
writing. When adding a new pattern: write `scripts/pattern_<x>.py` following
pattern_b.py's shape, write `pattern-<x>-groups.json` in the same card-dict
format, and register it in `index.html` (`DATASETS` map + a `.dsboxes`
checkbox with id `ds-<x>`). Then re-run `alternates.py` with the new file in
its argument list, or the new pattern's slots get no cycle arrows.

## Data vintage

The shipped datasets were not all built from the same bulk file:

- `pattern-a-groups.json`, `pattern-b-groups.json`, `pattern-c-groups.json`,
  `alternates.json` — built **2026-08-11** (oracle_cards
  `2026-08-11T21:01:58Z`, 38,626 cards, 350 creature types). Includes The
  Hobbit (`hob`/`hoc`, 2026-08-14).
- `groups.json`, `creature-groups.md`, `pasch-groups.json` — still from the
  **2026-07-09** build. They are deployed but no longer browsable, so the
  staleness is cosmetic; note it means Pasch's "all-3-subtype family of
  Pattern A" identity does not currently hold against the files on disk
  (233 shipped vs 234 in the current Pattern A run). Re-running `pasch.py`
  and `find_groups.py` realigns them.

Note the generators key the pool by subtype set and keep **one
representative card per set**, first-seen in bulk-file order. A new printing
can therefore change which card a group displays without changing the group
— when diffing datasets, compare subtype-set structures, not card names.
