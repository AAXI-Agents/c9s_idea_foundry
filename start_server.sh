#!/usr/bin/env bash
set -euo pipefail

# Start the FastAPI server.
# If NGROK_AUTHTOKEN is set, an ngrok tunnel will be opened.

# Load .env if present
if [[ -f .env ]]; then
	set -a
	source .env
	set +a
fi

# Fix SSL certs for macOS / pyenv (certifi CA bundle)
if [[ -z "${SSL_CERT_FILE:-}" ]]; then
	export SSL_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())" 2>/dev/null || true)
fi

if [[ -n "${NGROK_AUTHTOKEN:-}" ]]; then
	echo "Starting API with ngrok tunnel..."
	uv run start_api --ngrok
else
	echo "NGROK_AUTHTOKEN not set; starting API without ngrok."
	uv run start_api
fi