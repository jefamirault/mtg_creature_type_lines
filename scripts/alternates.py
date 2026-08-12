#!/usr/bin/env python3
"""Alternates: every card that could stand in for a card the browser shows.

The pattern generators keep one representative card per subtype set
(`reps.setdefault(...)`, first-seen in bulk-file order), so which Zombie Frog
Beast fills a slot is arbitrary. A group's structure depends only on the
subtype sets, so any card carrying those subtypes is an equally valid occupant
— this collects them so the UI can cycle a slot through them.

Matching is by **superset**, not equality: an Elf Soldier slot also accepts
Citanul Stalwart (Elf Druid Soldier), because it is still an Elf and still a
Soldier, which is all the group asks of that slot. The surplus subtypes are
recorded in `extra` so the UI can show them as outside the group's structure —
the group is defined by the slot's own set, and the type summary, chip colors
and Scryfall link stay keyed to that no matter which card is showing.

Scoped to the subtype sets the shipped datasets actually use; run it AFTER the
pattern generators, since it reads their output. Same Vintage/single-faced
filters as the generators — an alternate has to be a card that could have been
picked in the first place.

  python3 scripts/alternates.py data/oracle-cards.json data/creature-types.json \
      alternates.json pattern-a-groups.json pattern-b-groups.json pattern-c-groups.json
"""
import json
import sys

BULK, TYPES, OUT, DATASETS = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]

SKIP_LAYOUTS = {"token", "double_faced_token", "art_series", "emblem", "scheme",
                "planar", "vanguard",
                "transform", "modal_dfc", "meld", "reversible_card", "battle"}

creature_types = set(json.load(open(TYPES))["data"])
multiword = sorted((t for t in creature_types if " " in t), key=len, reverse=True)


def subtypes_of(type_line):
    if "—" not in type_line:
        return None
    left, right = type_line.split("—", 1)
    if "Creature" not in left.split():
        return None
    for phrase in multiword:
        right = right.replace(phrase, phrase.replace(" ", "_"))
    return frozenset(w.replace("_", " ") for w in right.split()
                     if w.replace("_", " ") in creature_types)


# The sets in play, plus the card each dataset currently shows for them — the
# latter is the drift check: if a displayed card is missing from its own set's
# alternates, this file was built from a different bulk snapshot.
used = set()
displayed = {}
for path in DATASETS:
    for group in json.load(open(path)):
        for card in group:
            subs = frozenset(card["subtypes"])
            used.add(subs)
            displayed.setdefault(subs, set()).add(card["name"])
print(f"subtype sets in use: {len(used)} (from {len(DATASETS)} datasets)")

# Every set in play that contains a given subtype. A card can only fill sets
# built entirely from its own subtypes, so this narrows the superset test to a
# handful of candidates instead of all 471 sets.
sets_by_type = {}
for s in used:
    for t in s:
        sets_by_type.setdefault(t, []).append(s)

alts = {s: [] for s in used}
for card in json.load(open(BULK)):
    if card.get("layout") in SKIP_LAYOUTS:
        continue
    if card.get("legalities", {}).get("vintage") not in ("legal", "restricted"):
        continue
    if card.get("card_faces"):
        parts = [(f.get("name", card["name"]), f.get("type_line", ""),
                  (f.get("image_uris") or card.get("image_uris") or {}))
                 for f in card["card_faces"]]
    else:
        parts = [(card["name"], card.get("type_line", ""),
                  card.get("image_uris") or {})]
    for name, tl, imgs in parts:
        subs = subtypes_of(tl)
        if not subs:
            continue
        for s in {x for t in subs for x in sets_by_type.get(t, ()) if x <= subs}:
            entry = {
                "name": name, "type_line": tl.strip(),
                "image": imgs.get("normal", ""),
                "url": card.get("scryfall_uri", ""),
            }
            if subs - s:
                entry["extra"] = sorted(subs - s)
            alts[s].append(entry)

for subs, cards in alts.items():
    assert cards, f"no card at all for {sorted(subs)}"
    names = {c["name"] for c in cards}
    missing = displayed[subs] - names
    assert not missing, (f"{sorted(missing)} shown for {sorted(subs)} but absent "
                         f"from the bulk file — rebuild the pattern datasets")

# Key on the sorted subtypes, which is exactly the `subtypes` array the UI
# already holds for the slot. Exact matches first, then by how many surplus
# subtypes they carry, then alphabetical — so cycling walks the cleanest fills
# before the ones that drag extra types along, and the order is stable.
data = {"|".join(sorted(s)):
        sorted(cards, key=lambda c: (len(c.get("extra", ())), c["name"]))
        for s, cards in alts.items()}
json.dump(data, open(OUT, "w"))
total = sum(len(v) for v in data.values())
widened = sum(1 for v in data.values() for c in v if "extra" in c)
cyclable = sum(1 for v in data.values() if len(v) > 1)
print(f"wrote {OUT}: {len(data)} sets, {total} cards "
      f"({widened} carrying extra subtypes), {cyclable} sets with alternates")

for key, cards in sorted(data.items(), key=lambda kv: -len(kv[1]))[:5]:
    print(f"  {len(cards):4d}  {key}")
