#!/usr/bin/env python3
"""Pattern B: 5 creatures / 5 subtypes matching the incidence structure
  123, 124, 345, 15, 25
(up to relabeling): A,B are 3-subtype cards sharing exactly {1,2};
C = {3,4,5} picks up the leftovers of A and B plus one new subtype 5;
D = {1,5} and E = {2,5} are 2-subtype cards. Every pair of cards shares
a subtype; nothing is shared by all. Vintage-legal, single-faced only."""
import json
import sys
from itertools import combinations

BULK, TYPES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

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


reps = {}
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
        if subs and len(subs) in (2, 3):
            reps.setdefault(subs, {
                "name": name, "type_line": tl.strip(),
                "image": imgs.get("normal", ""),
                "url": card.get("scryfall_uri", ""),
            })

three = [s for s in reps if len(s) == 3]
two = {s for s in reps if len(s) == 2}
print(f"3-subtype sets: {len(three)}, 2-subtype sets: {len(two)}")

# element-pair -> 3-sets containing both
by_pair = {}
for s in three:
    for pair in combinations(sorted(s), 2):
        by_pair.setdefault(pair, []).append(s)

found = {}
for key, sets_ab in by_pair.items():
    p, q = key
    # A, B: two 3-sets whose intersection is exactly {p, q}
    for a, b in combinations(sets_ab, 2):
        (r,) = a - {p, q}
        (s,) = b - {p, q}
        if r == s:
            continue
        # C contains r and s plus one subtype new to A∪B
        for c in by_pair.get(tuple(sorted((r, s))), []):
            (x,) = c - {r, s}
            if x in (p, q):
                continue
            d, e = frozenset((p, x)), frozenset((q, x))
            if d in two and e in two:
                g = (a, b, c, d, e)
                found[frozenset(g)] = g

print(f"pattern-B groups found: {len(found)}")

# verify against the example structure
for a, b, c, d, e in found.values():
    union = a | b | c | d | e
    assert len(union) == 5
    assert len(a & b) == 2 and len(d & e) == 1
    for pp, qq in combinations((a, b, c, d, e), 2):
        assert pp & qq
    assert not (a & b & c)

groups = sorted(found.values(),
                key=lambda g: sorted(reps[s]["name"] for s in g))
data = [[{**reps[s], "subtypes": sorted(s)}
         for s in sorted(g, key=lambda s: (-len(s), reps[s]["name"]))]
        for g in groups]
json.dump(data, open(OUT, "w"))
print(f"wrote {OUT}")

for g in groups[:5]:
    print()
    for s in sorted(g, key=lambda s: (-len(s), reps[s]["name"])):
        print(f"  {reps[s]['name']}  |  {reps[s]['type_line']}")
