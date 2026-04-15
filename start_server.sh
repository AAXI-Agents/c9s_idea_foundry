#!/usr/bin/env bash
set -euo pipefail

# Start the FastAPI server.
# SERVER_ENV controls the public URL strategy:
#   DEV  — starts ngrok tunnel (requires NGROK_AUTHTOKEN)
#   UAT  — uses DOMAIN_NAME_UAT (no tunnel)
#   PROD — uses DOMAIN_NAME_PROD (no tunnel)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Activate the virtual environment if not already active
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
	source "$SCRIPT_DIR/.venv/bin/activate"
fi

# Load .env if present
if [[ -f "$SCRIPT_DIR/.env" ]]; then
	set -a
	source "$SCRIPT_DIR/.env"
	set +a
fi

# Fix SSL certs for macOS / pyenv (certifi CA bundle)
if [[ -z "${SSL_CERT_FILE:-}" ]]; then
	_certifi_path=$(python3 -c "import certifi; print(certifi.where())" 2>/dev/null || true)
	if [[ -n "${_certifi_path:-}" ]]; then
		export SSL_CERT_FILE="$_certifi_path"
	fi
fi

ENV="${SERVER_ENV:-DEV}"

# Resolve port: DEV uses DOMAIN_NAME_DEV_PORT, others use API_PORT
if [[ "$ENV" == "DEV" ]]; then
	PORT="${DOMAIN_NAME_DEV_PORT:-8000}"
else
	PORT="${API_PORT:-8000}"
fi

# Kill any existing process on the API port
echo "Stopping any process on port $PORT..."
lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true

# NOTE: Do NOT kill ngrok here.  The Python startup code
# (ngrok_tunnel.py) cleanly disconnects tunnels via the local agent
# API before killing the process.  If we pkill ngrok first, the cloud
# never receives a clean disconnect and holds the static domain for
# 30-60 s (causing ERR_NGROK_334 on restart).

# Wait until the port is actually free (up to 5 seconds)
for i in {1..10}; do
	if ! lsof -ti:"$PORT" >/dev/null 2>&1; then
		break
	fi
	sleep 0.5
done

echo "SERVER_ENV=$ENV — starting API on port $PORT..."
uv run start_api --port "$PORT"