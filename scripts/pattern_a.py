#!/usr/bin/env python3
"""Pattern A: exactly 4 creatures, unique type lines, every pair shares a
subtype, no subtype common to all four, and >= 6 distinct subtypes that each
appear on at least 2 of the cards. Vintage-legal, single-faced cards only.

That needs >= 12 subtype slots over 4 cards, which splits the search into
two exhaustive families:
- all four cards have 3 subtypes (1-subtype cards can never join a valid
  group, and 2s can't reach 12 slots without a 4): then there are exactly
  12 slots, so exactly 6 subtypes each on exactly 2 cards and every pair
  sharing exactly 1 — the K4/Pasch structure, enumerated by forced
  completion exactly as in pasch.py;
- at least one card has 4+ subtypes: such subtype sets are rare (16 as of
  Jul 2026), so each anchors an exhaustive scan of the sets intersecting it.
Unlike the old >= 6-distinct-subtypes definition, this is small enough to
enumerate fully — no sampling."""
import json
import sys
from collections import Counter
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


def shared_twice(group):
    """Subtypes appearing on at least 2 of the group's cards."""
    freq = Counter(t for s in group for t in s)
    return [t for t, n in freq.items() if n >= 2]


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

found = {}

# ---- family 1: all four cards 3-subtype — the K4/Pasch structure
three = [s for s in nodes if len(s) == 3]
by_pair = {}
for s in three:
    for pair in combinations(sorted(s), 2):
        by_pair.setdefault(pair, []).append(s)

for a in three:
    for b in three:
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
                    if d in reps and d not in (a, b, c):
                        g = frozenset((a, b, c, d))
                        found.setdefault(g, list(g))

print(f"family 1 (all 3-subtype, Pasch structure): {len(found)}")

# ---- family 2: anchored on the rare 4+-subtype sets
tid = {t: i for i, t in enumerate(sorted(creature_types))}
def mask(s):
    m = 0
    for t in s:
        m |= 1 << tid[t]
    return m

M = {s: mask(s) for s in nodes}
anchors = [s for s in nodes if len(s) >= 4]
print(f"4+-subtype anchor sets: {len(anchors)}")

for s1 in anchors:
    m1 = M[s1]
    C1 = [(M[s], s) for s in nodes if s != s1 and M[s] & m1]
    for i, (m2, s2) in enumerate(C1):
        C12 = [(m, s) for m, s in C1[i + 1:] if m & m2]
        m12 = m1 & m2
        for j, (m3, s3) in enumerate(C12):
            p3 = m12 | (m1 & m3) | (m2 & m3)   # subtypes on 2+ of s1..s3
            u3 = m1 | m2 | m3
            c123 = m12 & m3
            for m4, s4 in C12[j + 1:]:
                if not (m3 & m4) or (c123 & m4):
                    continue
                if bin(p3 | (m4 & u3)).count("1") >= 6:
                    found.setdefault(frozenset((s1, s2, s3, s4)),
                                     [s1, s2, s3, s4])

print(f"pattern-A groups total (exhaustive): {len(found)}")

# verify
for g in found:
    assert len(g) == 4
    assert len(shared_twice(g)) >= 6
    assert all(p & q for p, q in combinations(g, 2))
    a, b, c, d = g
    assert not (a & b & c & d)

# prefer variety: sort by shared then total subtypes (desc), then limit overlap
ranked = sorted(found.values(),
                key=lambda g: (-len(shared_twice(g)),
                               -len(frozenset().union(*g)),
                               sorted(reps[s]["name"] for s in g)))
kept, kept_names = [], []
for g in ranked:
    names = frozenset(reps[s]["name"] for s in g)
    # near-duplicate = shares 3+ of its 4 cards with some already-kept group
    if any(len(names & kn) > 2 for kn in kept_names):
        continue
    kept.append(g)
    kept_names.append(names)
    if len(kept) >= CAP:
        break

print(f"kept for browser: {len(kept)}; shared-twice counts "
      f"{len(shared_twice(kept[0]))} (max) .. {len(shared_twice(kept[-1]))} (min)")

data = [[{**reps[s], "subtypes": sorted(s)}
         for s in sorted(g, key=lambda s: reps[s]["name"])] for g in kept]
json.dump(data, open(OUT, "w"))
print(f"wrote {OUT}")

for g in kept[:4]:
    print(f"\n--- {len(shared_twice(g))} subtypes shared twice+, "
          f"union {len(frozenset().union(*g))} ---")
    for s in sorted(g, key=lambda s: reps[s]["name"]):
        print(f"  {reps[s]['name']}  |  {reps[s]['type_line']}")
