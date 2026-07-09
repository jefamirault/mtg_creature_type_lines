#!/usr/bin/env python3
"""Find groups of creatures with unique type lines where every pair shares
at least one creature subtype. Groups must have >= 4 members."""
import json
import random
import sys
from collections import Counter

BULK, TYPES = sys.argv[1], sys.argv[2]

SKIP_LAYOUTS = {"token", "double_faced_token", "art_series", "emblem", "scheme",
                "planar", "vanguard",
                # double-faced layouts excluded per catalog rules
                "transform", "modal_dfc", "meld", "reversible_card", "battle"}

creature_types = set(json.load(open(TYPES))["data"])
multiword = sorted((t for t in creature_types if " " in t), key=len, reverse=True)


def faces(card):
    if card.get("card_faces"):
        for f in card["card_faces"]:
            if f.get("type_line"):
                img = (f.get("image_uris") or card.get("image_uris") or {}).get("normal", "")
                yield f.get("name", card["name"]), f["type_line"], img
    elif card.get("type_line"):
        img = (card.get("image_uris") or {}).get("normal", "")
        yield card["name"], card["type_line"], img


def subtypes_of(type_line):
    if "—" not in type_line:
        return None
    left, right = type_line.split("—", 1)
    if "Creature" not in left.split():
        return None
    for phrase in multiword:
        right = right.replace(phrase, phrase.replace(" ", "_"))
    return frozenset(w.replace("_", " ") for w in right.split() if w.replace("_", " ") in creature_types)


# distinct type line -> (subtype set, representative card, image, scryfall url)
lines = {}
for card in json.load(open(BULK)):
    if card.get("layout") in SKIP_LAYOUTS:
        continue
    if card.get("legalities", {}).get("vintage") not in ("legal", "restricted"):
        continue
    for face_name, tl, img in faces(card):
        subs = subtypes_of(tl)
        if subs:
            lines.setdefault(tl.strip(), (subs, face_name, img,
                                          card.get("scryfall_uri", "")))

print(f"distinct creature type lines with subtypes: {len(lines)}")

# ---- trivial groups: all members share one subtype ----
by_subtype = Counter()
for tl, (subs, *_rest) in lines.items():
    for s in subs:
        by_subtype[s] += 1
eligible = {s: n for s, n in by_subtype.items() if n >= 4}
print(f"subtypes that can anchor a trivial group (>=4 distinct type lines): {len(eligible)} of {len(by_subtype)}")
print("  biggest anchors:", by_subtype.most_common(5))

# ---- interesting groups: pairwise intersecting, but empty common intersection ----
# Only type lines with >=2 subtypes can participate (a 1-subtype line forces
# its subtype on every other member, i.e. a common subtype).
# For variety, keep one representative type line per distinct subtype SET.
by_set = {}
for tl, (subs, rep, img, url) in lines.items():
    if len(subs) >= 2:
        by_set.setdefault(subs, (tl, rep, img, url))
nodes = [(tl, subs, rep) for subs, (tl, rep, img, url) in by_set.items()]
card_info = {tl: (img, url) for subs, (tl, rep, img, url) in by_set.items()}
print(f"nodes for interesting-group search (distinct subtype sets, >=2 subtypes): {len(nodes)}")

random.seed(42)
found = {}  # frozenset of type lines -> group
for trial in range(20000):
    random.shuffle(nodes)
    group = []
    inter = None
    for tl, subs, rep in nodes:
        if all(subs & g[1] for g in group):
            new_inter = subs if inter is None else (inter & subs)
            group.append((tl, subs, rep))
            inter = new_inter
            if len(group) >= 8:
                break
    # trim from the front until common intersection is empty? No: greedy grew a
    # clique; keep it only if no subtype is shared by ALL members.
    if len(group) >= 4 and not inter:
        key = frozenset(g[0] for g in group)
        found[key] = group

groups = sorted(found.values(), key=len, reverse=True)
print(f"\ninteresting groups found (pairwise share a subtype, none shared by all): {len(found)}")
sizes = Counter(len(g) for g in groups)
print("  sizes:", dict(sorted(sizes.items(), reverse=True)))

if len(sys.argv) > 3:
    with open(sys.argv[3], "w") as f:
        f.write("# Creature groups: unique type lines, every pair shares a subtype,\n")
        f.write("# and NO subtype is shared by all members (non-trivial groups)\n\n")
        for i, g in enumerate(groups, 1):
            f.write(f"## Group {i} (size {len(g)})\n")
            for tl, subs, rep in sorted(g, key=lambda x: x[0]):
                f.write(f"- {rep} — `{tl}`\n")
            f.write("\n")

if len(sys.argv) > 4:
    out = []
    for g in groups:
        out.append([{
            "name": rep,
            "type_line": tl,
            "subtypes": sorted(subs),
            "image": card_info[tl][0],
            "url": card_info[tl][1],
        } for tl, subs, rep in sorted(g, key=lambda x: x[0])])
    with open(sys.argv[4], "w") as f:
        json.dump(out, f)
    print(f"wrote {len(out)} groups to {sys.argv[4]}")

seen_lines = set()
shown = 0
for g in groups:
    key = frozenset(x[0] for x in g)
    if key & seen_lines:  # prefer diverse examples
        continue
    seen_lines |= key
    shown += 1
    print(f"\n--- group of {len(g)} ---")
    for tl, subs, rep in sorted(g, key=lambda x: x[0]):
        print(f"  {rep}  |  {tl}")
    if shown >= 6:
        break
