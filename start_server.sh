#!/usr/bin/env bash
set -euo pipefail

# Start the FastAPI server.
# If NGROK_AUTHTOKEN is set, an ngrok tunnel will be opened.

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

PORT="${API_PORT:-8000}"

# Kill any existing process on the API port and ngrok
echo "Stopping any process on port $PORT..."
lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
lsof -ti:4040 | xargs kill -9 2>/dev/null || true
pkill -f "ngrok" 2>/dev/null || true

# Wait until the port is actually free (up to 5 seconds)
for i in {1..10}; do
	if ! lsof -ti:"$PORT" >/dev/null 2>&1; then
		break
	fi
	sleep 0.5
done

if [[ -n "${NGROK_AUTHTOKEN:-}" ]]; then
	echo "Starting API with ngrok tunnel on port $PORT..."
	uv run start_api --ngrok --port "$PORT"
else
	echo "NGROK_AUTHTOKEN not set; starting API without ngrok on port $PORT."
	uv run start_api --port "$PORT"
fi