#!/usr/bin/env python3
"""Creatures with 3+ subtypes: the browser's Creatures view and the Moxfield lists.

Every card that meets the base rules (Vintage-legal, no double-faced layouts,
subtypes validated against the creature-types catalog) and has a creature face
with 3+ subtypes. Each card is shown as its **first paper printing**: the
earliest `released_at` among its paper, non-oversized printings, preferring a
non-promo printing on a tie (prerelease and store promos share the set's date),
then the lowest collector number. That needs every printing, so it reads
Scryfall's default_cards bulk file as well as oracle_cards.

Writes:
  creatures-3plus.json             the browser dataset: a flat list of cards,
                                   each `name, type_line, subtypes, image, url,
                                   set, cn, released`, ordered by subtype count
                                   (desc) then name
  <moxdir>/moxfield-3plus-part1.txt   3-subtype cards A–M
  <moxdir>/moxfield-3plus-part2.txt   3-subtype cards N–Z, then all 4+
                                   (Moxfield lists choke past ~1,000 cards)
  Moxfield lines are `1 Name (SET) CN #N-subtypes`.

  python3 scripts/creatures_3plus.py data/oracle-cards.json data/creature-types.json \\
      data/default-cards.jsonl.gz creatures-3plus.json moxfield
"""
import gzip
import json
import os
import re
import sys
from collections import Counter

BULK, TYPES, PRINTINGS, OUT, MOXDIR = sys.argv[1:6]

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


# oracle_id -> the card's best creature face (most subtypes; flip and adventure
# cards are parsed face by face, as in every other generator)
eligible = {}
for card in json.load(open(BULK)):
    if card.get("layout") in SKIP_LAYOUTS:
        continue
    if card.get("legalities", {}).get("vintage") not in ("legal", "restricted"):
        continue
    if card.get("card_faces"):
        parts = [f.get("type_line", "") for f in card["card_faces"]]
    else:
        parts = [card.get("type_line", "")]
    best = max(((subtypes_of(tl) or frozenset(), tl.strip()) for tl in parts),
               key=lambda p: len(p[0]))
    if len(best[0]) >= 3:
        eligible[card["oracle_id"]] = {
            # Moxfield and the UI both want the front face's name, not "A // B"
            "name": card["name"].split(" // ")[0],
            "subtypes": best[0], "type_line": best[1],
        }
print(f"eligible creatures with 3+ subtypes: {len(eligible)}")


def cn_key(p):
    m = re.match(r"\d+", p["collector_number"])
    return (int(m.group()) if m else 0, p["collector_number"])


first = {}
with gzip.open(PRINTINGS, "rt") as f:
    for line in f:
        line = line.strip().rstrip(",")
        if not line or line in "[]":
            continue
        p = json.loads(line)
        if p.get("oracle_id") not in eligible:
            continue
        if "paper" not in p.get("games", []) or p.get("oversized"):
            continue
        key = (p["released_at"], bool(p.get("promo")), cn_key(p))
        if p["oracle_id"] not in first or key < first[p["oracle_id"]][0]:
            first[p["oracle_id"]] = (key, p)

missing = [c["name"] for o, c in eligible.items() if o not in first]
assert not missing, f"no paper printing found for: {missing}"

cards = []
for oid, c in eligible.items():
    p = first[oid][1]
    imgs = p.get("image_uris") or (p.get("card_faces") or [{}])[0].get("image_uris") or {}
    cards.append({
        "name": c["name"], "type_line": c["type_line"],
        "subtypes": sorted(c["subtypes"]),
        "image": imgs.get("normal", ""),
        "url": p.get("scryfall_uri", ""),
        "set": p["set"].upper(), "cn": p["collector_number"],
        "released": p["released_at"],
    })
cards.sort(key=lambda c: (-len(c["subtypes"]), c["name"]))

# verify before writing
names = [c["name"] for c in cards]
assert len(names) == len(set(names)), "duplicate card names"
for c in cards:
    assert len(c["subtypes"]) >= 3, c
    assert all(s in creature_types for s in c["subtypes"]), c
    assert c["image"] and c["url"] and c["set"] and c["cn"], c

json.dump(cards, open(OUT, "w"))
print(f"wrote {OUT}")


def mox(c):
    return f"1 {c['name']} ({c['set']}) {c['cn']} #{len(c['subtypes'])}-subtypes"


by_name = sorted(cards, key=lambda c: c["name"])
three = [c for c in by_name if len(c["subtypes"]) == 3]
more = sorted((c for c in cards if len(c["subtypes"]) > 3),
              key=lambda c: (len(c["subtypes"]), c["name"]))
part1 = [c for c in three if c["name"][0].upper() <= "M"]
part2 = [c for c in three if c["name"][0].upper() > "M"] + more
assert len(part1) + len(part2) == len(cards)
os.makedirs(MOXDIR, exist_ok=True)
for i, part in enumerate((part1, part2), 1):
    path = os.path.join(MOXDIR, f"moxfield-3plus-part{i}.txt")
    with open(path, "w") as f:
        f.write("".join(mox(c) + "\n" for c in part))
    print(f"wrote {path} ({len(part)} cards)")

for n, k in sorted(Counter(len(c["subtypes"]) for c in cards).items(), reverse=True):
    print(f"  {n} subtypes: {k} cards")
