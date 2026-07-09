#!/usr/bin/env bash
# Serve the site locally for development.
#   ./local_server.sh        # http://localhost:8123
#   ./local_server.sh 9000   # custom port (or set LOCAL_PORT in .env)
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
PORT="${1:-${LOCAL_PORT:-8123}}"
echo "Serving $(pwd) at http://localhost:${PORT}/ (Ctrl+C to stop)"
exec python3 -m http.server "$PORT"
