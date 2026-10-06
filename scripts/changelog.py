#!/usr/bin/env python3
"""Changelog: what a data refresh changed, for the browser's "What's new" panel.

Diffs the freshly generated pattern datasets against the previous build's
copies (read from git, HEAD by default) and prepends one entry to
changelog.json. Groups are compared by **structure** — the multiset of subtype
sets — never by card names, since a refresh can swap a group's representative
card without changing the group.

A refresh that adds or removes no group in any pattern writes nothing: the
panel only reports refreshes that changed the groups. Re-running for the same
build replaces that build's entry, so this is safe to repeat.

Run it AFTER the pattern generators (and alternates.py), BEFORE committing the
regenerated datasets — HEAD still holds the previous build then:

  python3 scripts/changelog.py data/oracle-cards.json data/SOURCE.txt changelog.json card-ledger.txt

Options:
  --prev REF     git revision holding the previous datasets (default HEAD)
  --since DATE   previous build's Scryfall date (YYYY-MM-DD...); only needed
                 when changelog.json has no entry yet to take it from

"New" cards are the Vintage-legal cards missing from the previous build's
card-ledger.txt (one card name per line, also read from git). The ledger is
rewritten on every run, changed groups or not, and committed with the
datasets. Release dates are no good for this: sets can go legal before their
official release date, so a set can already be in one build and still carry a
later date. With no ledger in git yet (first run only), it falls back to
non-reprint cards released after --since from sets the previous build's
datasets do not already show.

Every group gets a stable ID (see group_id) that index.html computes the same
way, so a bookmarked group link survives later refreshes reordering the
datasets. Keep the two implementations in sync.
"""
import argparse
import json
import subprocess
import sys

DATASETS = {"a": "pattern-a-groups.json", "b": "pattern-b-groups.json",
            "c": "pattern-c-groups.json"}


def fnv1a32(s):
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def structure(group):
    """Canonical string for a group: its sorted subtype sets."""
    return "/".join(sorted("|".join(sorted(c["subtypes"])) for c in group))


def group_ids(ds, groups):
    """Stable ID per group, in dataset order — must match index.html groupIds().

    `g<ds>-<8 hex>` from an FNV-1a hash of the dataset key and the structure.
    Two groups with the same structure in one dataset (possible only in
    Pattern C, which keys its pool by color identity too) get -2, -3, … in
    dataset order.
    """
    seen, ids = {}, []
    for g in groups:
        base = f"g{ds}-{fnv1a32(ds + ':' + structure(g)):08x}"
        seen[base] = seen.get(base, 0) + 1
        ids.append(base if seen[base] == 1 else f"{base}-{seen[base]}")
    return ids


def read_source(path):
    out = {}
    for line in open(path):
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bulk")
    ap.add_argument("source")
    ap.add_argument("out")
    ap.add_argument("ledger")
    ap.add_argument("--prev", default="HEAD")
    ap.add_argument("--since")
    args = ap.parse_args()

    try:
        log = json.load(open(args.out))
    except FileNotFoundError:
        log = []

    src = read_source(args.source)
    updated = src["oracle_cards updated"]
    build = updated[:10]
    # entries are newest first; the one for this build (on a re-run) doesn't count
    older = [e for e in log if e["build"] != build]
    since = args.since or (older[0]["scryfall_updated"] if older else None)
    if not since:
        sys.exit("no previous changelog entry — pass --since <previous build date>")
    since_day = since[:10]

    def git_show(path):
        try:
            return subprocess.run(["git", "show", f"{args.prev}:{path}"],
                                  check=True, capture_output=True, text=True).stdout
        except subprocess.CalledProcessError:
            return None

    prev_data = {ds: json.loads(git_show(path) or "[]") for ds, path in DATASETS.items()}
    prev_ledger = git_show(args.ledger)
    if prev_ledger is not None:
        known = set(prev_ledger.splitlines())
        is_new = lambda c: c["name"] not in known
    else:
        # sets the previous build demonstrably had, from its card URLs
        old_sets = {c["url"].split("/")[4] for groups in prev_data.values()
                    for g in groups for c in g}
        old_alts = json.loads(git_show("alternates.json") or "{}")
        old_sets |= {c["url"].split("/")[4] for v in old_alts.values() for c in v}
        is_new = lambda c: (not c.get("reprint") and c.get("released_at", "") > since_day
                            and c["set"] not in old_sets)
        print(f"no {args.ledger} at {args.prev}: falling back to release dates")

    # New releases: Vintage-legal cards the previous build did not have.
    new_cards, sets, ledger = {}, {}, set()
    for card in json.load(open(args.bulk)):
        if card.get("legalities", {}).get("vintage") not in ("legal", "restricted"):
            continue
        ledger.add(card["name"])
        if not is_new(card):
            continue
        new_cards[card["name"]] = card
        s = sets.setdefault(card["set"], {"set": card["set"], "name": card["set_name"],
                                          "released": card["released_at"],
                                          "cards": 0, "creatures": 0})
        s["cards"] += 1
        s["creatures"] += any("Creature" in part.split("—")[0].split()
                              for part in card.get("type_line", "").split("//"))

    def slim(card):
        out = {k: card[k] for k in ("name", "type_line", "subtypes", "url")}
        if card["name"] in new_cards:
            out["new"] = True
        return out

    patterns, changed = {}, False
    for ds, path in DATASETS.items():
        cur, prev = json.load(open(path)), prev_data[ds]
        cur_ids, prev_ids = group_ids(ds, cur), group_ids(ds, prev)
        assert len(set(cur_ids)) == len(cur_ids), f"duplicate group id in {path}"
        old, now = dict(zip(prev_ids, prev)), dict(zip(cur_ids, cur))
        added = [{"id": i, "cards": [slim(c) for c in now[i]]} for i in cur_ids if i not in old]
        removed = [{"id": i, "cards": [slim(c) for c in old[i]]} for i in prev_ids if i not in now]
        changed |= bool(added or removed)
        patterns[ds] = {"before": len(prev), "after": len(cur),
                        "added": added, "removed": removed}
        print(f"pattern {ds}: {len(prev)} -> {len(cur)}  +{len(added)} -{len(removed)}")

    with open(args.ledger, "w") as f:
        f.write("".join(n + "\n" for n in sorted(ledger)))
    print(f"wrote {args.ledger} ({len(ledger)} cards)")

    if not changed:
        print("no groups added or removed — changelog left as is")
        return

    entry = {
        "build": build,
        "scryfall_updated": updated,
        "since": since,
        "cards": int(src["cards in file"]),
        "releases": sorted(sets.values(), key=lambda s: (s["released"], s["name"]), reverse=True),
        "patterns": patterns,
    }
    contributing = sorted({c["name"] for p in patterns.values() for g in p["added"]
                           for c in g["cards"] if c.get("new")})
    print(f"new releases since {since_day}: {len(new_cards)} cards in {len(sets)} sets; "
          f"in new groups: {', '.join(contributing) or 'none'}")

    log = [entry] + older
    with open(args.out, "w") as f:
        json.dump(log, f, indent=1)
        f.write("\n")
    print(f"wrote {args.out} ({len(log)} entries)")


if __name__ == "__main__":
    main()
