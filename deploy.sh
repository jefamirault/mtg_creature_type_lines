#!/usr/bin/env bash
#
# Deploy the site to the nginx server (rsync over SSH).
# Server settings come from .env (see .env.example).
#
# Usage:
#   ./deploy.sh            # deploy
#   ./deploy.sh --dry-run  # show what would change, transfer nothing
set -euo pipefail
cd "$(dirname "$0")"

[[ -f .env ]] || { echo "Missing .env — copy .env.example and fill it in." >&2; exit 1; }
set -a; source .env; set +a

: "${DEPLOY_USER:?DEPLOY_USER not set in .env}"
: "${DEPLOY_HOST:?DEPLOY_HOST not set in .env}"
: "${DEPLOY_PATH:?DEPLOY_PATH not set in .env}"
: "${DEPLOY_DOMAIN:?DEPLOY_DOMAIN not set in .env}"

# Only the files the site actually serves — anything not listed here never
# reaches the server, so scripts/ / CLAUDE.md / deploy.sh / .env stay local.
FILES=(index.html groups.json pattern-a-groups.json pattern-b-groups.json pattern-c-groups.json pasch-groups.json)

# ── Deploy stamp ─────────────────────────────────────────────────────────────
# Ship a deploy.json alongside the site so "what's live?" is answerable from
# outside — the status dashboard reads it over plain https, and so can you.
# Timestamp + short SHA + branch leak nothing actionable; keep it public.
# Degrades to no stamp outside a git checkout rather than failing the deploy.
if git rev-parse HEAD >/dev/null 2>&1; then
  DIRTY=false; git diff --quiet HEAD -- 2>/dev/null || DIRTY=true
  printf '{"deployed_at":"%s","commit":"%s","branch":"%s","dirty":%s}\n' \
    "$(date -u +%FT%TZ)" "$(git rev-parse --short HEAD)" \
    "$(git rev-parse --abbrev-ref HEAD)" "$DIRTY" > deploy.json
  FILES+=(deploy.json)
fi

for f in "${FILES[@]}"; do
  [[ -e "$f" ]] || { echo "missing file: $f" >&2; exit 1; }
done

# --delete keeps the server an exact mirror of the allowlist.
# --no-owner/--no-group: the deploy user can't chown files created by other
# users on the server, and nginx doesn't care who owns them.
RSYNC_OPTS=(-avz --delete --no-owner --no-group)
if [[ "${1:-}" == "--dry-run" || "${1:-}" == "-n" ]]; then
  RSYNC_OPTS+=(--dry-run)
  echo "── dry run: no files will be transferred ──"
fi

echo "Deploying to ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/ (${DEPLOY_DOMAIN})"
rsync "${RSYNC_OPTS[@]}" "${FILES[@]}" "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/"

echo "Done. → https://${DEPLOY_DOMAIN}/"
