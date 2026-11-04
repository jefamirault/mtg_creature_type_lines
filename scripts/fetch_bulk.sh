#!/usr/bin/env bash
# Download the Scryfall inputs the generators need into data/ (gitignored).
#
#   ./scripts/fetch_bulk.sh
#
# Writes data/oracle-cards.json, data/default-cards.jsonl.gz,
# data/creature-types.json, data/SOURCE.txt.
# Scryfall serves bulk data only as gzipped JSONL, so the oracle file is
# converted to a JSON array here — that is the shape the generators expect
# (they all do json.load(open(BULK))). default_cards (every printing, needed
# only by creatures_3plus.py to find each card's first printing) stays gzipped
# JSONL — it is read line by line.
set -euo pipefail
cd "$(dirname "$0")/.."

UA="mtg-type-line-groups/1.0 (jeffreyamirault@gmail.com)"
DATA=data
mkdir -p "$DATA"

echo "==> querying https://api.scryfall.com/bulk-data"
meta=$(curl -sS -H "User-Agent: $UA" -H "Accept: application/json" \
  https://api.scryfall.com/bulk-data)

bulk_entry() {   # bulk_entry <type> -> "<jsonl uri> <updated_at>"
  printf '%s' "$meta" | python3 -c '
import json, sys
for e in json.load(sys.stdin)["data"]:
    if e["type"] == sys.argv[1]:
        print(e["jsonl_download_uri"], e["updated_at"])
        break
else:
    sys.exit("no " + sys.argv[1] + " entry in /bulk-data")
' "$1"
}
read -r URI UPDATED < <(bulk_entry oracle_cards)
read -r DURI DUPDATED < <(bulk_entry default_cards)
echo "    oracle_cards updated $UPDATED"
echo "    $URI"

echo "==> downloading + converting to a JSON array (this takes a minute)"
curl -sS --fail -H "User-Agent: $UA" "$URI" \
  | gzip -dc \
  | python3 -c '
import json, sys
json.dump([json.loads(line) for line in sys.stdin if line.strip()],
          open(sys.argv[1], "w"))
' "$DATA/oracle-cards.json"
echo "    wrote $DATA/oracle-cards.json ($(du -h "$DATA/oracle-cards.json" | cut -f1))"

echo "==> downloading default_cards (every printing; kept gzipped)"
echo "    default_cards updated $DUPDATED"
curl -sS --fail -H "User-Agent: $UA" "$DURI" -o "$DATA/default-cards.jsonl.gz"
echo "    wrote $DATA/default-cards.jsonl.gz ($(du -h "$DATA/default-cards.jsonl.gz" | cut -f1))"

echo "==> downloading creature-types catalog"
curl -sS --fail -H "User-Agent: $UA" -H "Accept: application/json" \
  https://api.scryfall.com/catalog/creature-types -o "$DATA/creature-types.json"
TYPES=$(python3 -c 'import json;print(json.load(open("data/creature-types.json"))["total_values"])')
CARDS=$(python3 -c 'import json;print(len(json.load(open("data/oracle-cards.json"))))')
echo "    $TYPES creature types"

cat > "$DATA/SOURCE.txt" <<EOF
oracle_cards download : $URI
oracle_cards updated  : $UPDATED
cards in file         : $CARDS
default_cards download: $DURI
default_cards updated : $DUPDATED
creature types        : $TYPES
fetched at            : $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
echo "==> done; provenance in $DATA/SOURCE.txt"
