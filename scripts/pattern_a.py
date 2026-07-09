#!/usr/bin/env python3
"""Pattern A: exactly 4 creatures, unique type lines, every pair shares a
subtype, no subtype common to all four, and >= 6 distinct subtypes total.
Vintage-legal, single-faced cards only. The space is too large to enumerate,
so sample it and keep a diverse, deduplicated selection."""
import json
import random
import sys
from itertools import combinations

BULK, TYPES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
CAP = 600  # keep the browser dataset manageable

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


reps = {}  # subtype set -> card info (one representative per distinct set)
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
        # 1-subtype cards can't join: their subtype would end up common to all
        if subs and len(subs) >= 2:
            reps.setdefault(subs, {
                "name": name, "type_line": tl.strip(),
                "image": imgs.get("normal", ""),
                "url": card.get("scryfall_uri", ""),
            })

nodes = list(reps)
print(f"candidate subtype sets: {len(nodes)}")

random.seed(7)
found = {}
for trial in range(150000):
    seed = random.choice(nodes)
    group = [seed]
    # random order each trial for diversity
    for s in random.sample(nodes, 60):
        if len(group) == 4:
            break
        if s not in group and all(s & g for g in group):
            group.append(s)
    if len(group) != 4:
        continue
    union = frozenset().union(*group)
    common = group[0]
    for s in group[1:]:
        common = common & s
    if len(union) >= 6 and not common:
        found[frozenset(group)] = group

print(f"pattern-A groups sampled (deduplicated): {len(found)}")

# verify
for g in found:
    assert len(g) == 4
    assert len(frozenset().union(*g)) >= 6
    assert all(p & q for p, q in combinations(g, 2))
    a, b, c, d = g
    assert not (a & b & c & d)

# prefer variety: sort by total distinct subtypes (desc), then limit overlap
ranked = sorted(found.values(),
                key=lambda g: (-len(frozenset().union(*g)),
                               sorted(reps[s]["name"] for s in g)))
kept, used = [], set()
for g in ranked:
    names = frozenset(reps[s]["name"] for s in g)
    if len(names & used) > 2:  # skip near-duplicates of kept groups
        continue
    kept.append(g)
    used |= names
    if len(kept) >= CAP:
        break

print(f"kept for browser: {len(kept)}; union sizes "
      f"{len(frozenset().union(*kept[0]))} (max) .. {len(frozenset().union(*kept[-1]))} (min)")

data = [[{**reps[s], "subtypes": sorted(s)}
         for s in sorted(g, key=lambda s: reps[s]["name"])] for g in kept]
json.dump(data, open(OUT, "w"))
print(f"wrote {OUT}")

for g in kept[:4]:
    print(f"\n--- union of {len(frozenset().union(*g))} subtypes ---")
    for s in sorted(g, key=lambda s: reps[s]["name"]):
        print(f"  {reps[s]['name']}  |  {reps[s]['type_line']}")
