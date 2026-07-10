#!/usr/bin/env bash
# Serve the site locally for development.
#   ./local_server.sh          # http://localhost:8123
#   ./local_server.sh 9000     # custom port (positional)
#   ./local_server.sh -p 3000  # custom port (flag; or set LOCAL_PORT in .env)
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f .env ]]; then set -a; source .env; set +a; fi

PORT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--port) PORT="$2"; shift 2 ;;
    -p*)       PORT="${1#-p}"; shift ;;
    --port=*)  PORT="${1#--port=}"; shift ;;
    -h|--help) echo "Usage: $0 [-p PORT] [PORT]"; exit 0 ;;
    *)         PORT="$1"; shift ;;
  esac
done
PORT="${PORT:-${LOCAL_PORT:-8123}}"
echo "Serving $(pwd) at http://localhost:${PORT}/ (Ctrl+C to stop)"
exec python3 -m http.server "$PORT"
