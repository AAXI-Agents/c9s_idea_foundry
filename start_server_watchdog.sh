#!/usr/bin/env bash
set -euo pipefail

# ─── Watchdog wrapper for start_server.sh ────────────────────
#
# Restarts the server automatically if it exits unexpectedly.
# Respects SIGINT/SIGTERM for clean shutdown (no restart).
#
# Usage:
#   ./start_server_watchdog.sh              # default 5s restart delay
#   RESTART_DELAY=10 ./start_server_watchdog.sh  # custom delay
#
# Logs restarts to logs/watchdog.log alongside the application log.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESTART_DELAY="${RESTART_DELAY:-5}"
MAX_RAPID_RESTARTS="${MAX_RAPID_RESTARTS:-5}"
RAPID_WINDOW="${RAPID_WINDOW:-120}"  # seconds

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
WATCHDOG_LOG="$LOG_DIR/watchdog.log"

# Track rapid restart count
declare -a restart_times=()

_log() {
    local msg
    msg="$(date '+%Y-%m-%d %H:%M:%S') | WATCHDOG | $1"
    echo "$msg"
    echo "$msg" >> "$WATCHDOG_LOG"
}

# ── Signal handling ──────────────────────────────────────────
_shutdown=0
_child_pid=0

_on_signal() {
    _shutdown=1
    _log "Received shutdown signal — stopping server (PID=$_child_pid)"
    if [[ $_child_pid -ne 0 ]]; then
        kill -TERM "$_child_pid" 2>/dev/null || true
        wait "$_child_pid" 2>/dev/null || true
    fi
    _log "Watchdog stopped"
    exit 0
}

trap _on_signal INT TERM

# ── Rapid-restart circuit breaker ────────────────────────────
_check_rapid_restarts() {
    local now
    now=$(date +%s)

    # Prune entries older than the window
    local pruned=()
    for ts in "${restart_times[@]}"; do
        if (( now - ts < RAPID_WINDOW )); then
            pruned+=("$ts")
        fi
    done
    restart_times=("${pruned[@]}")

    # Add current restart
    restart_times+=("$now")

    if (( ${#restart_times[@]} >= MAX_RAPID_RESTARTS )); then
        _log "CIRCUIT BREAKER: $MAX_RAPID_RESTARTS restarts in ${RAPID_WINDOW}s — stopping watchdog"
        exit 1
    fi
}

# ── Main loop ────────────────────────────────────────────────
_log "Watchdog started (restart_delay=${RESTART_DELAY}s, max_rapid=${MAX_RAPID_RESTARTS}/${RAPID_WINDOW}s)"

while true; do
    _log "Starting server..."

    # Run start_server.sh in background so we can trap signals
    "$SCRIPT_DIR/start_server.sh" &
    _child_pid=$!

    # Wait for the child process
    set +e
    wait "$_child_pid"
    exit_code=$?
    set -e
    _child_pid=0

    # If we received a shutdown signal, don't restart
    if [[ $_shutdown -eq 1 ]]; then
        break
    fi

    # Exit code 0 means clean shutdown — don't restart
    if [[ $exit_code -eq 0 ]]; then
        _log "Server exited cleanly (code 0) — not restarting"
        break
    fi

    _log "Server crashed with exit code $exit_code"

    # Check circuit breaker
    _check_rapid_restarts

    _log "Restarting in ${RESTART_DELAY}s..."
    sleep "$RESTART_DELAY"
done

_log "Watchdog exiting"
