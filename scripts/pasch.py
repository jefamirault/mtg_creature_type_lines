#!/usr/bin/env python3
"""Find Pasch-configuration creature groups: 4 creatures, 3 subtypes each,
6 distinct subtypes total — every subtype on exactly 2 creatures, every
pair of creatures sharing exactly 1 subtype (pattern 123/145/246/356).
Vintage-legal, single-faced cards only."""
import json
import sys
from itertools import combinations

BULK, TYPES = sys.argv[1], sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 else None

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


# subtype set (exactly 3) -> representative card
reps = {}
for card in json.load(open(BULK)):
    if card.get("layout") in SKIP_LAYOUTS:
        continue
    if card.get("legalities", {}).get("vintage") not in ("legal", "restricted"):
        continue
    # parse faces separately: flip/split/adventure cards are single-faced
    # physically, but their combined type line mixes both halves' subtypes
    if card.get("card_faces"):
        parts = [(f.get("name", card["name"]), f.get("type_line", ""),
                  (f.get("image_uris") or card.get("image_uris") or {}))
                 for f in card["card_faces"]]
    else:
        parts = [(card["name"], card.get("type_line", ""),
                  card.get("image_uris") or {})]
    for name, tl, imgs in parts:
        subs = subtypes_of(tl)
        if subs and len(subs) == 3:
            reps.setdefault(subs, {
                "name": name, "type_line": tl.strip(),
                "image": imgs.get("normal", ""),
                "url": card.get("scryfall_uri", ""),
            })

sets = list(reps)
print(f"distinct 3-subtype sets (vintage-legal, single-faced): {len(sets)}")

# index: pair of subtypes -> sets containing both
by_pair = {}
for s in sets:
    for pair in combinations(sorted(s), 2):
        by_pair.setdefault(pair, []).append(s)

found = set()
for a in sets:
    for b in sets:
        if a >= b:  # unordered
            continue
        common = a & b
        if len(common) != 1:
            continue
        (x,) = common
        a1, a2 = sorted(a - common)
        b1, b2 = sorted(b - common)
        # C: one subtype from a-side, one from b-side, one brand new
        for ai in (a1, a2):
            for bj in (b1, b2):
                for c in by_pair.get(tuple(sorted((ai, bj))), []):
                    if c == a or c == b or x in c:
                        continue
                    if len(c & a) != 1 or len(c & b) != 1:
                        continue
                    new = c - a - b
                    if len(new) != 1:
                        continue
                    # D is forced: the three subtypes seen exactly once
                    d = frozenset({a1, a2, b1, b2} - {ai, bj} | new)
                    dd = frozenset(d)
                    if dd in reps and dd not in (a, b, c):
                        found.add(frozenset((a, b, c, dd)))

print(f"Pasch groups found: {len(found)}")

# sanity check every group
for g in found:
    g = list(g)
    assert all(len(s) == 3 for s in g)
    assert len(frozenset().union(*g)) == 6
    assert all(len(p & q) == 1 for p, q in combinations(g, 2))

groups = sorted(found, key=lambda g: sorted(reps[s]["name"] for s in g))
if OUT:
    data = [[{**reps[s], "subtypes": sorted(s)}
             for s in sorted(g, key=lambda s: reps[s]["name"])] for g in groups]
    json.dump(data, open(OUT, "w"))
    print(f"wrote {OUT}")

for g in list(groups)[:10]:
    print()
    for s in sorted(g, key=lambda s: reps[s]["name"]):
        r = reps[s]
        print(f"  {r['name']}  |  {r['type_line']}")
