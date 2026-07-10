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
  (334 types). This handles the multi-word subtype "Time Lord" and drops
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
  scan). 399 groups; near-dupes (3+ shared cards vs a kept group) dropped
  for the browser (325 kept), sorted by shared-subtype then union count desc.
- **Pattern B**: `123 / 124 / 345 / 15 / 25` — 5 creatures / 5 subtypes;
  exhaustively enumerated (242 groups).
- **Pasch**: `123 / 145 / 246 / 356` — 4 creatures / 6 subtypes, every subtype
  on exactly 2 cards, every pair sharing exactly 1; exhaustive (233 groups).
  Exactly the all-3-subtype family of Pattern A (233 of its 399 groups).
- **Pattern C (CMR Partners)**: Pattern A/B groups anchored on two Commander
  Legends partner cards — one matching `set:cmr o:partner c:w`, a different
  card matching `set:cmr o:partner` (anchor lists fetched from the Scryfall
  search API at runtime). The anchors are the commander pair: the remaining
  cards must fit within the union of the anchors' color identities, so the
  pool tracks one card per (subtype set, color identity). With two slots
  pinned, pattern A is enumerated exhaustively; pattern B is exhaustive and
  empty (no B group contains two partner subtype sets even before the
  identity filter). Under the ≥6-subtypes-shared-twice Pattern A definition
  the dataset is **currently empty** — partner anchors are too small to
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
  card image (filter to groups with that card), card name links to Scryfall,
  per-group favorites (localStorage, keyed by dataset + sorted card names)
  with a favorites-only filter, a Stats toggle (synced to `?stats=1`) showing
  per-pattern subtype instance counts, and an Export button downloading the
  currently shown groups as a text file. Every group gets a deck-building
  Scryfall link — `-is:digital -is:reprint` plus one `(t:x or t:y …)` clause
  per creature, i.e. cards sharing a subtype with every group member.
- `groups.json`, `pattern-a-groups.json`, `pattern-b-groups.json`,
  `pattern-c-groups.json`, `pasch-groups.json` — datasets: arrays of groups;
  each card has `name, type_line, subtypes, image, url`. The UI fetches only
  the Pattern A/B/C files; `groups.json` and `pasch-groups.json` are kept
  (and still deployed) but no longer browsable.
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

Ships only `index.html` + the five dataset JSONs (allowlist in `deploy.sh`);
`scripts/`, docs, CSV, and `.env` never leave this machine. Content deploys
need no nginx reload. After regenerating a dataset, just deploy again.

## Workflows

Regenerating data needs the Scryfall bulk file (~170 MB, not kept in the
project). Get the current URL from `https://api.scryfall.com/bulk-data`
(type `oracle_cards`) and download it, plus the creature types catalog from
`https://api.scryfall.com/catalog/creature-types` (save the JSON response).
Send a `User-Agent` header on Scryfall API requests; prefer bulk data over
paging `/cards/search` for dataset work.

    python3 scripts/find_groups.py  <bulk.json> <creature-types.json> creature-groups.md groups.json
    python3 scripts/pattern_a.py    <bulk.json> <creature-types.json> pattern-a-groups.json
    python3 scripts/pattern_b.py    <bulk.json> <creature-types.json> pattern-b-groups.json
    python3 scripts/pattern_c.py    <bulk.json> <creature-types.json> pattern-c-groups.json
    python3 scripts/pasch.py        <bulk.json> <creature-types.json> pasch-groups.json
    python3 scripts/catalog_subtypes.py <bulk.json> <creature-types.json> creatures-3plus-subtypes.csv

All generators verify their structural constraints with assertions before
writing. When adding a new pattern: write `scripts/pattern_<x>.py` following
pattern_b.py's shape, write `pattern-<x>-groups.json` in the same card-dict
format, and register it in `index.html` (`DATASETS` map + a `.dsboxes`
checkbox with id `ds-<x>`).
