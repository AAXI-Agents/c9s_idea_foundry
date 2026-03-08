#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# dev_setup.sh — One-command project bootstrap for new developers
#
# Usage:
#   ./scripts/dev_setup.sh
#
# What it does:
#   1. Creates a Python virtual environment (.venv) if missing
#   2. Installs project dependencies (uv or pip)
#   3. Copies .env.example → .env if .env doesn't exist
#   4. Runs MongoDB collection bootstrap (if MONGODB_URI is set)
#   5. Ensures VS Code settings reference CODEX.md for Copilot
#   6. Prints next steps
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "══════════════════════════════════════════════════"
echo "  CrewAI Product Feature Planner — Dev Setup"
echo "══════════════════════════════════════════════════"
echo ""

# ── 1. Virtual environment ──────────────────────────────────
if [[ ! -d ".venv" ]]; then
    echo "Creating virtual environment (.venv)..."
    python3 -m venv .venv
    echo "  Done."
else
    echo "Virtual environment already exists (.venv)."
fi

source .venv/bin/activate

# ── 2. Install dependencies ─────────────────────────────────
echo ""
echo "Installing dependencies..."
if command -v uv &>/dev/null; then
    uv pip install -e ".[dev]" 2>/dev/null || uv pip install -e .
    echo "  Installed via uv."
else
    pip install -e . --quiet
    echo "  Installed via pip."
fi

# ── 3. Copy .env.example → .env ─────────────────────────────
echo ""
if [[ ! -f ".env" ]]; then
    if [[ -f ".env.example" ]]; then
        cp .env.example .env
        echo "Copied .env.example → .env"
        echo "  ⚠  Edit .env and fill in your API keys before starting the server."
    else
        echo "No .env.example found — skipping .env creation."
    fi
else
    echo ".env already exists — skipping copy."
fi

# ── 4. MongoDB collection bootstrap ─────────────────────────
echo ""
if [[ -f ".env" ]]; then
    set -a
    source .env
    set +a
fi

if [[ -n "${MONGODB_URI:-}${MONGODB_HOST:-}" ]]; then
    echo "Bootstrapping MongoDB collections and indexes..."
    python -m crewai_productfeature_planner.scripts.setup_mongodb && \
        echo "  Done." || \
        echo "  Skipped (MongoDB not reachable — configure MONGODB_URI in .env)."
else
    echo "MONGODB_URI not set — skipping MongoDB bootstrap."
    echo "  Set it in .env and run:"
    echo "  python -m crewai_productfeature_planner.scripts.setup_mongodb"
fi

# ── 5. VS Code configuration ─────────────────────────────────
echo ""
echo "VS Code settings configured:"
echo "  .vscode/settings.json → CODEX.md as Copilot instruction file"
echo "  .github/copilot-instructions.md → references CODEX.md"
if [[ ! -f ".vscode/extensions.json" ]]; then
    cat > .vscode/extensions.json << 'EXTJSON'
{
    "recommendations": [
        "ms-python.python",
        "ms-python.debugpy",
        "github.copilot",
        "github.copilot-chat"
    ]
}
EXTJSON
    echo "  Created .vscode/extensions.json with recommended extensions."
else
    echo "  .vscode/extensions.json already exists."
fi

# ── 6. Next steps ───────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "    1. Edit .env with your API keys"
echo "    2. Start the server:  ./start_server.sh"
echo "    3. Run tests:         .venv/bin/python -m pytest -x -q"
echo "    4. Open in VS Code:   code ."
echo ""
echo "  CODEX.md is configured as the Copilot instruction file."
echo "  Copilot Chat will automatically use project conventions"
echo "  defined in CODEX.md for code generation and assistance."
echo "══════════════════════════════════════════════════"
