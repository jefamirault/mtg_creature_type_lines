#!/usr/bin/env python3
"""Pattern C ("partners"): pattern A/B groups anchored on two Commander
Legends partner cards — one matching Scryfall `set:cmr o:partner c:w`, a
different card matching `set:cmr o:partner`. Both anchor lists are fetched
from the Scryfall search API at runtime (they are tiny).

The two anchors are the commander pair, so the remaining cards must fit
within the union of the anchors' color identities. The pool therefore keeps
one candidate card per (subtype set, color identity); a set is usable for a
given anchor pair only if some card with that set fits the pair's identity.

With two of the four slots pinned, pattern A is enumerated exhaustively:
every pair shares a subtype, no subtype common to all, >=6 distinct
subtypes that each appear on 2+ of the cards, unique type lines. Results
are ranked and near-dupes dropped, as in pattern_a.py. Pattern B is also checked exhaustively; as of Jul 2026 no
pattern-B group contains both anchors even before the color-identity
filter, but any future hits are appended. Vintage-legal, single-faced."""
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from itertools import combinations


def shared_twice(group):
    """Subtypes appearing on at least 2 of the group's cards."""
    freq = Counter(t for s in group for t in s)
    return [t for t, n in freq.items() if n >= 2]

BULK, TYPES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
CAP = 600

QUERY_W = "set:cmr o:partner c:w"
QUERY_Y = "set:cmr o:partner"

SKIP_LAYOUTS = {"token", "double_faced_token", "art_series", "emblem", "scheme",
                "planar", "vanguard",
                "transform", "modal_dfc", "meld", "reversible_card", "battle"}

CI_BIT = {c: 1 << i for i, c in enumerate("WUBRG")}

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


def ci_mask(card):
    m = 0
    for c in card.get("color_identity", []):
        m |= CI_BIT[c]
    return m


def scryfall_search(query):
    url = ("https://api.scryfall.com/cards/search?q="
           + urllib.parse.quote(query))
    cards = []
    while url:
        req = urllib.request.Request(url, headers={
            "User-Agent": "mtg-type-line-groups/1.0", "Accept": "application/json"})
        page = json.load(urllib.request.urlopen(req))
        cards += page["data"]
        url = page.get("next_page") if page.get("has_more") else None
    return cards


def anchor_cards(cards):
    """Anchors need 2+ subtypes: a single subtype would be shared by, hence
    common to, the whole group."""
    out = []
    for c in cards:
        subs = subtypes_of(c.get("type_line", ""))
        if not subs or len(subs) < 2:
            continue
        out.append({
            "name": c["name"], "type_line": c["type_line"].strip(),
            "image": (c.get("image_uris") or {}).get("normal", ""),
            "url": c.get("scryfall_uri", ""),
            "subs": subs, "ci": ci_mask(c),
        })
    return out


anchors_w = anchor_cards(scryfall_search(QUERY_W))
anchors_y = anchor_cards(scryfall_search(QUERY_Y))
print(f"anchor cards: W {len(anchors_w)}, any {len(anchors_y)}")

# ---- pool: subtype set -> {color identity mask -> representative card}
pool = {}
for card in json.load(open(BULK)):
    if card.get("layout") in SKIP_LAYOUTS:
        continue
    if card.get("legalities", {}).get("vintage") not in ("legal", "restricted"):
        continue
    ci = ci_mask(card)
    if card.get("card_faces"):
        parts = [(f.get("name", card["name"]), f.get("type_line", ""),
                  (f.get("image_uris") or card.get("image_uris") or {}))
                 for f in card["card_faces"]]
    else:
        parts = [(card["name"], card.get("type_line", ""),
                  card.get("image_uris") or {})]
    for name, tl, imgs in parts:
        subs = subtypes_of(tl)
        if subs and len(subs) >= 2:
            pool.setdefault(subs, {}).setdefault(ci, {
                "name": name, "type_line": tl.strip(),
                "image": imgs.get("normal", ""),
                "url": card.get("scryfall_uri", ""),
            })

# only minimal identity masks matter: if a set has a card of identity m2 ⊂ m,
# the m card is redundant for any allowed-identity check
for s, byci in pool.items():
    for m in [m for m in byci
              if any(m2 != m and m2 & m == m2 for m2 in byci)]:
        del byci[m]

nodes = list(pool)
print(f"pool: {len(nodes)} distinct multi-subtype sets")
for c in anchors_w + anchors_y:
    assert c["subs"] in pool, f"anchor set missing from pool: {sorted(c['subs'])}"


def repname(s):
    return min(c["name"] for c in pool[s].values())


def fitting(s, allowed):
    """A pool card with subtype set s inside the allowed color identity."""
    return next((c for m, c in sorted(pool[s].items())
                 if not m & ~allowed), None)


def render(group_sets, wcard, ycard, allowed):
    cards = []
    for s in group_sets:
        if s == wcard["subs"]:
            c = wcard
        elif s == ycard["subs"]:
            c = ycard
        else:
            c = fitting(s, allowed)
            if c is None:
                return None
        cards.append({"name": c["name"], "type_line": c["type_line"],
                      "image": c["image"], "url": c["url"],
                      "subtypes": sorted(s)})
    if len({c["type_line"] for c in cards}) != len(cards):
        return None
    # the two commanders lead the group, then the rest alphabetically
    commanders = {wcard["name"], ycard["name"]}
    return sorted(cards, key=lambda c: (c["name"] not in commanders, c["name"]))


# anchor pairs: distinct cards, distinct subtype sets (same set ⇒ identical
# CMR legend type lines), sharing a subtype
apairs = [(wc, yc) for wc in anchors_w for yc in anchors_y
          if wc["name"] != yc["name"] and wc["subs"] != yc["subs"]
          and wc["subs"] & yc["subs"]]
print(f"viable anchor card pairs: {len(apairs)}")

# ---- pattern A, anchored: choose s3, s4 within the pair's color identity
tid = {t: i for i, t in enumerate(sorted(creature_types))}
def mask(s):
    m = 0
    for t in s:
        m |= 1 << tid[t]
    return m

node_masks = [(mask(s), s) for s in nodes]

found_a = {}  # (frozenset of 4 sets, allowed CI) -> (wcard, ycard)
count = 0
for wc, yc in apairs:
    ws, ys = wc["subs"], yc["subs"]
    allowed = wc["ci"] | yc["ci"]
    wm, ym = mask(ws), mask(ys)
    base, common_wy = wm | ym, wm & ym
    C = [(m, s) for m, s in node_masks if m & wm and m & ym
         and s != ws and s != ys and fitting(s, allowed)]
    for i, (m3, s3) in enumerate(C):
        p3 = common_wy | (wm & m3) | (ym & m3)  # subtypes on 2+ of first three
        c3, u3 = common_wy & m3, base | m3
        for m4, s4 in C[i + 1:]:
            if not (m3 & m4) or (c3 & m4):
                continue
            if bin(p3 | (m4 & u3)).count("1") < 6:  # >=6 subtypes on 2+ cards
                continue
            count += 1
            found_a.setdefault((frozenset((ws, ys, s3, s4)), allowed), (wc, yc))

print(f"pattern-A: {count:,} valid combinations, {len(found_a):,} distinct groups")

ranked = sorted(found_a.items(),
                key=lambda kv: (-len(shared_twice(kv[0][0])),
                                -len(frozenset().union(*kv[0][0])),
                                sorted(repname(s) for s in kv[0][0])))
kept, used = [], set()
for (gsets, allowed), (wc, yc) in ranked:
    cards = render(sorted(gsets, key=repname), wc, yc, allowed)
    if cards is None:
        continue
    names = frozenset(c["name"] for c in cards)
    if len(names & used) > 2:  # skip near-duplicates of kept groups
        continue
    kept.append((gsets, allowed, cards))
    used |= names
    if len(kept) >= CAP:
        break

print(f"pattern-A kept after dedupe/cap: {len(kept)}")

for gsets, allowed, cards in kept:
    assert len(gsets) == 4 and len(cards) == 4
    assert len(shared_twice(gsets)) >= 6
    assert all(p & q for p, q in combinations(gsets, 2))
    a, b, c, d = gsets
    assert not (a & b & c & d)
    assert len({cc["type_line"] for cc in cards}) == 4
    assert len({cc["name"] for cc in cards}) == 4
    anchor_names = {c["name"] for c in anchors_w} | {c["name"] for c in anchors_y}
    for cc in cards:
        if cc["name"] not in anchor_names:
            m = min(m for m in pool[frozenset(cc["subtypes"])]
                    if pool[frozenset(cc["subtypes"])][m]["name"] == cc["name"])
            assert not m & ~allowed

# ---- pattern B, exhaustive (see pattern_b.py), filtered to anchor pairs
three = [s for s in nodes if len(s) == 3]
two = {s for s in nodes if len(s) == 2}
by_pair = {}
for s in three:
    for pair in combinations(sorted(s), 2):
        by_pair.setdefault(pair, []).append(s)

found_b = {}
for (p, q), sets_ab in by_pair.items():
    for a, b in combinations(sets_ab, 2):
        (r,) = a - {p, q}
        (s,) = b - {p, q}
        if r == s:
            continue
        for c in by_pair.get(tuple(sorted((r, s))), []):
            (x,) = c - {r, s}
            if x in (p, q):
                continue
            d, e = frozenset((p, x)), frozenset((q, x))
            if d in two and e in two:
                found_b[frozenset((a, b, c, d, e))] = None

b_kept = []
for g in found_b:
    for wc, yc in apairs:
        if wc["subs"] not in g or yc["subs"] not in g:
            continue
        cards = render(sorted(g, key=repname), wc, yc, wc["ci"] | yc["ci"])
        if cards:
            b_kept.append((g, cards))
            break

print(f"pattern-B: {len(found_b)} groups total, {len(b_kept)} with both anchors")

for g, cards in b_kept:
    union = frozenset().union(*g)
    assert len(g) == 5 and len(union) == 5
    assert all(p & q for p, q in combinations(g, 2))
    assert not frozenset.intersection(*g)
    assert len({cc["type_line"] for cc in cards}) == 5

json.dump([cards for *_, cards in kept] + [cards for _, cards in b_kept],
          open(OUT, "w"))
print(f"wrote {OUT}")

for gsets, allowed, cards in kept[:4]:
    ci = "".join(c for c in "WUBRG" if allowed & CI_BIT[c]) or "C"
    print(f"\n--- {len(shared_twice(gsets))} subtypes shared twice+, "
          f"union {len(frozenset().union(*gsets))}, identity {ci} ---")
    for c in cards:
        print(f"  {c['name']}  |  {c['type_line']}")
