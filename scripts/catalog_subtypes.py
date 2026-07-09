#!/usr/bin/env python3
"""Catalog creature cards with 3+ official creature subtypes from Scryfall bulk data."""
import csv
import json
import sys
from collections import Counter

BULK, TYPES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

# Layouts that aren't real playable cards
SKIP_LAYOUTS = {"token", "double_faced_token", "art_series", "emblem", "scheme",
                "planar", "vanguard"}

creature_types = set(json.load(open(TYPES))["data"])
# Multi-word types (e.g. "Time Lord") need phrase matching before word-splitting
multiword = sorted((t for t in creature_types if " " in t), key=len, reverse=True)


def faces(card):
    if card.get("card_faces"):
        for f in card["card_faces"]:
            if f.get("type_line"):
                yield f.get("name", card["name"]), f["type_line"]
    elif card.get("type_line"):
        yield card["name"], card["type_line"]


def subtypes_of(type_line):
    """Return list of official creature subtypes if this face is a Creature."""
    if "—" not in type_line:
        return None
    left, right = type_line.split("—", 1)
    if "Creature" not in left.split():
        return None
    for phrase in multiword:
        right = right.replace(phrase, phrase.replace(" ", "_"))
    words = [w.replace("_", " ") for w in right.split()]
    return [w for w in words if w in creature_types]


cards = json.load(open(BULK))
rows = []
for card in cards:
    if card.get("layout") in SKIP_LAYOUTS:
        continue
    for face_name, type_line in faces(card):
        subs = subtypes_of(type_line)
        if subs and len(subs) >= 3:
            rows.append({
                "name": card["name"],
                "face": face_name,
                "type_line": type_line,
                "subtype_count": len(subs),
                "subtypes": ", ".join(subs),
                "set": card.get("set", ""),
                "rarity": card.get("rarity", ""),
                "scryfall_uri": card.get("scryfall_uri", ""),
            })

rows.sort(key=lambda r: (-r["subtype_count"], r["name"]))
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

print(f"creature faces with 3+ official subtypes: {len(rows)}")
for count, n in sorted(Counter(r["subtype_count"] for r in rows).items(), reverse=True):
    print(f"  {count} subtypes: {n} cards")
print("\ntop of catalog:")
for r in rows[:12]:
    print(f"  [{r['subtype_count']}] {r['face']}: {r['type_line']}")
