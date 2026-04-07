#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# dev_setup.sh — Deployment startup & validation script
#
# Usage:
#   ./scripts/dev_setup.sh              # auto-detect from DEPLOY_ENV
#   ./scripts/dev_setup.sh uat          # UAT environment
#   ./scripts/dev_setup.sh prod         # Production environment
#   ./scripts/dev_setup.sh dev          # Local development (legacy)
#
# What it does:
#   1. Detects or accepts the deployment environment (dev/uat/prod)
#   2. Validates the Python virtual environment exists
#   3. Loads and validates all required environment variables
#   4. Verifies MongoDB Atlas connectivity with TLS/SSL
#   5. Pings the Atlas cluster domain name (DNS + network)
#   6. Bootstraps MongoDB collections and indexes
#   7. Validates LLM provider API keys
#   8. Validates Atlassian integrations (Confluence, Jira)
#   9. Prints deployment readiness summary
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# ── Colour helpers (no-op if not a TTY) ─────────────────────
if [[ -t 1 ]]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; RESET=''
fi

pass()  { echo -e "  ${GREEN}✔${RESET} $1"; }
fail()  { echo -e "  ${RED}✘${RESET} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${RESET} $1"; }
info()  { echo -e "  ${CYAN}ℹ${RESET} $1"; }
header(){ echo -e "\n${BOLD}── $1 ──${RESET}"; }

FAILURES=0
WARNINGS=0

record_fail() { ((FAILURES++)) || true; fail "$1"; }
record_warn() { ((WARNINGS++)) || true; warn "$1"; }

# ── 1. Resolve deployment environment ───────────────────────
ENV_ARG="${1:-}"
if [[ -n "$ENV_ARG" ]]; then
    DEPLOY_ENV="$ENV_ARG"
else
    DEPLOY_ENV="${DEPLOY_ENV:-dev}"
fi
DEPLOY_ENV=$(echo "$DEPLOY_ENV" | tr '[:upper:]' '[:lower:]')

case "$DEPLOY_ENV" in
    dev|uat|prod|production|staging)
        ;;
    *)
        echo -e "${RED}Error: Unknown environment '$DEPLOY_ENV'.${RESET}"
        echo "  Valid values: dev, uat, prod"
        exit 1
        ;;
esac

# Normalise aliases
[[ "$DEPLOY_ENV" == "production" ]] && DEPLOY_ENV="prod"
[[ "$DEPLOY_ENV" == "staging" ]]    && DEPLOY_ENV="uat"

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  CrewAI Product Feature Planner — Deployment Validator"
echo "  Environment: $(echo "$DEPLOY_ENV" | tr '[:lower:]' '[:upper:]')"
echo "  Date:        $(date '+%Y-%m-%d %H:%M:%S')"
echo "══════════════════════════════════════════════════════════"

# ── 2. Virtual environment ──────────────────────────────────
header "Python Environment"

if [[ ! -d ".venv" ]]; then
    if [[ "$DEPLOY_ENV" == "dev" ]]; then
        info "Creating virtual environment (.venv)..."
        python3 -m venv .venv
        pass "Virtual environment created"
    else
        record_fail "Virtual environment (.venv) not found — run setup in dev first"
    fi
else
    pass "Virtual environment exists (.venv)"
fi

if [[ -d ".venv" ]]; then
    source .venv/bin/activate
    PYTHON_VER=$(.venv/bin/python3 --version 2>&1 || echo "unknown")
    pass "Python: $PYTHON_VER"
fi

# Install deps in dev mode only
if [[ "$DEPLOY_ENV" == "dev" ]]; then
    info "Installing dependencies..."
    if command -v uv &>/dev/null; then
        uv pip install -e ".[dev]" 2>/dev/null || uv pip install -e .
        pass "Dependencies installed (uv)"
    else
        pip install -e . --quiet
        pass "Dependencies installed (pip)"
    fi
fi

# ── 3. Load and validate .env ───────────────────────────────
header "Environment Configuration"

if [[ -f ".env" ]]; then
    set -a
    source .env
    set +a
    pass ".env file loaded"
else
    record_fail ".env file not found"
fi

# Fix SSL certs for macOS / pyenv (certifi CA bundle)
if [[ -z "${SSL_CERT_FILE:-}" ]]; then
    _certifi_path=$(.venv/bin/python3 -c "import certifi; print(certifi.where())" 2>/dev/null || true)
    if [[ -n "${_certifi_path:-}" ]]; then
        export SSL_CERT_FILE="$_certifi_path"
        pass "SSL_CERT_FILE set to certifi bundle"
    else
        record_warn "Could not locate certifi CA bundle"
    fi
else
    pass "SSL_CERT_FILE already set"
fi

# ── Required environment variables by tier ──────────────────
# Core vars required for ALL environments
REQUIRED_CORE=(
    "MONGODB_ATLAS_URI"
    "MONGODB_DB"
    "DEFAULT_AGENT"
)

# LLM provider — at least one pair required
REQUIRED_LLM_OPENAI=(
    "OPENAI_API_KEY"
)
REQUIRED_LLM_GEMINI=(
    "GOOGLE_API_KEY"
)

# UAT/PROD additionally require Slack and Atlassian
REQUIRED_UAT_PROD=(
    "SLACK_SIGNING_SECRET"
    "SLACK_CLIENT_ID"
    "SLACK_CLIENT_SECRET"
    "ATLASSIAN_BASE_URL"
    "ATLASSIAN_USERNAME"
    "ATLASSIAN_API_TOKEN"
)

# PROD requires Confluence and Jira project keys
REQUIRED_PROD=(
    "CONFLUENCE_SPACE_KEY"
    "JIRA_PROJECT_KEY"
)

header "Required Environment Variables — Core"
for var in "${REQUIRED_CORE[@]}"; do
    val="${!var:-}"
    if [[ -z "$val" ]]; then
        record_fail "$var is not set"
    else
        pass "$var is set"
    fi
done

# LLM — check that at least one provider is configured
header "Required Environment Variables — LLM Provider"
has_openai=false
has_gemini=false

for var in "${REQUIRED_LLM_OPENAI[@]}"; do
    val="${!var:-}"
    [[ -n "$val" ]] && has_openai=true
done
for var in "${REQUIRED_LLM_GEMINI[@]}"; do
    val="${!var:-}"
    [[ -n "$val" ]] && has_gemini=true
done

if $has_openai; then
    pass "OpenAI API key configured"
else
    info "OpenAI API key not set"
fi
if $has_gemini; then
    pass "Google Gemini API key configured"
else
    info "Google Gemini API key not set"
fi
if ! $has_openai && ! $has_gemini; then
    record_fail "No LLM provider configured — set OPENAI_API_KEY or GOOGLE_API_KEY"
fi

# UAT/PROD tier checks
if [[ "$DEPLOY_ENV" == "uat" || "$DEPLOY_ENV" == "prod" ]]; then
    header "Required Environment Variables — $DEPLOY_ENV tier"
    for var in "${REQUIRED_UAT_PROD[@]}"; do
        val="${!var:-}"
        if [[ -z "$val" ]]; then
            record_fail "$var is not set (required for $DEPLOY_ENV)"
        else
            pass "$var is set"
        fi
    done
fi

if [[ "$DEPLOY_ENV" == "prod" ]]; then
    header "Required Environment Variables — Production"
    for var in "${REQUIRED_PROD[@]}"; do
        val="${!var:-}"
        if [[ -z "$val" ]]; then
            record_fail "$var is not set (required for production)"
        else
            pass "$var is set"
        fi
    done

    # Production should not have debug enabled
    if [[ "${CREWAI_DEBUG:-}" == "true" ]]; then
        record_warn "CREWAI_DEBUG=true in production (consider disabling)"
    fi
    if [[ "${CREWAI_VERBOSE:-}" == "true" ]]; then
        record_warn "CREWAI_VERBOSE=true in production (consider disabling)"
    fi
fi

# ── SSO Authentication ──────────────────────────────────────
header "SSO Authentication"

SSO_ON="${SSO_ENABLED:-false}"
SSO_ON=$(echo "$SSO_ON" | tr '[:upper:]' '[:lower:]')

if [[ "$SSO_ON" == "true" || "$SSO_ON" == "1" || "$SSO_ON" == "yes" ]]; then
    pass "SSO_ENABLED=true"

    if [[ -z "${SSO_BASE_URL:-}" ]]; then
        record_fail "SSO_BASE_URL is not set (required when SSO is enabled)"
    else
        pass "SSO_BASE_URL is set"
    fi

    if [[ -z "${SSO_CLIENT_ID:-}" ]]; then
        record_fail "SSO_CLIENT_ID is not set (required for OAuth login/register)"
    else
        pass "SSO_CLIENT_ID is set"
    fi

    if [[ -z "${SSO_CLIENT_SECRET:-}" ]]; then
        record_fail "SSO_CLIENT_SECRET is not set (required for OAuth token exchange)"
    else
        pass "SSO_CLIENT_SECRET is set"
    fi

    if [[ -n "${SSO_JWT_PUBLIC_KEY_PATH:-}" ]]; then
        if [[ -f "${SSO_JWT_PUBLIC_KEY_PATH}" ]]; then
            pass "SSO_JWT_PUBLIC_KEY_PATH points to existing file"
        else
            record_warn "SSO_JWT_PUBLIC_KEY_PATH is set but file not found (will use remote introspection)"
        fi
    else
        info "SSO_JWT_PUBLIC_KEY_PATH not set — will use remote introspection"
    fi
else
    info "SSO_ENABLED is not set or false — SSO auth bypassed (dev mode)"
fi

# DEV + ngrok: validate ngrok vars
if [[ "$DEPLOY_ENV" == "dev" ]]; then
    header "Ngrok (DEV Tunnel)"

    if [[ -n "${NGROK_DOMAIN:-}" ]]; then
        pass "NGROK_DOMAIN is set (${NGROK_DOMAIN})"
    else
        info "NGROK_DOMAIN not set — ngrok will assign a random URL each restart"
    fi

    if [[ -z "${NGROK_AUTHTOKEN:-}" ]]; then
        record_warn "NGROK_AUTHTOKEN not set — ngrok tunnel will fail when SERVER_ENV=DEV (set in .env)"
    else
        pass "NGROK_AUTHTOKEN is set"
    fi
fi

# ── 4. MongoDB Atlas — DNS & network ping ───────────────────
header "MongoDB Atlas — Network Connectivity"

ATLAS_URI="${MONGODB_ATLAS_URI:-}"
if [[ -n "$ATLAS_URI" ]]; then
    # Extract the cluster domain from the URI
    # mongodb+srv://user:pass@cluster.domain.net/... → cluster.domain.net
    ATLAS_DOMAIN=$(echo "$ATLAS_URI" | sed -E 's|^mongodb(\+srv)?://[^@]*@([^/?]+).*|\2|')

    if [[ -n "$ATLAS_DOMAIN" && "$ATLAS_DOMAIN" != "$ATLAS_URI" ]]; then
        pass "Atlas domain extracted: $ATLAS_DOMAIN"

        # DNS resolution check
        if host "$ATLAS_DOMAIN" &>/dev/null; then
            pass "DNS resolution: $ATLAS_DOMAIN resolves"
        else
            record_fail "DNS resolution failed for $ATLAS_DOMAIN"
        fi

        # Network ping (ICMP may be blocked on Atlas — use TCP SYN on port 27017 as fallback)
        if ping -c 1 -W 5 "$ATLAS_DOMAIN" &>/dev/null; then
            pass "ICMP ping: $ATLAS_DOMAIN reachable"
        else
            warn "ICMP ping failed (may be blocked by firewall — checking TLS…)"
        fi
    else
        record_fail "Could not extract domain from MONGODB_ATLAS_URI"
    fi
else
    record_fail "MONGODB_ATLAS_URI is not set — cannot check connectivity"
fi

# ── 5. MongoDB Atlas — TLS/SSL connection & ping ────────────
header "MongoDB Atlas — TLS/SSL Connection"

if [[ -n "$ATLAS_URI" ]]; then
    # Use Python + pymongo for proper TLS/SSL verification and Atlas ping
    MONGO_CHECK=$(.venv/bin/python3 -c "
import ssl
import sys
import certifi
from pymongo import MongoClient
from pymongo.errors import PyMongoError

uri = '''${ATLAS_URI}'''
db_name = '${MONGODB_DB:-ideas}'

try:
    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=10000,
        tls=True,
        tlsCAFile=certifi.where(),
    )
    # Verify connection + SSL handshake
    result = client.admin.command('ping')
    if result.get('ok') == 1.0:
        print('PING_OK')
    else:
        print('PING_FAIL:unexpected ping response')

    # Verify the target database is accessible
    db = client[db_name]
    collections = db.list_collection_names()
    print(f'DB_OK:{db_name}:{len(collections)} collections')

    # Get server info for build version
    info = client.server_info()
    print(f'SERVER:{info.get(\"version\", \"unknown\")}')

    # Check TLS details
    nodes = client.nodes
    if nodes:
        print(f'NODES:{len(nodes)} node(s) in cluster')

    client.close()
except PyMongoError as e:
    print(f'MONGO_ERROR:{e}')
    sys.exit(1)
except Exception as e:
    print(f'ERROR:{e}')
    sys.exit(1)
" 2>&1) || true

    if echo "$MONGO_CHECK" | grep -q "PING_OK"; then
        pass "MongoDB Atlas ping successful (TLS/SSL verified)"
    else
        error_detail=$(echo "$MONGO_CHECK" | grep -E "MONGO_ERROR|ERROR" | head -1)
        record_fail "MongoDB Atlas connection failed: ${error_detail:-unknown error}"
    fi

    if echo "$MONGO_CHECK" | grep -q "DB_OK"; then
        db_info=$(echo "$MONGO_CHECK" | grep "DB_OK" | sed 's/DB_OK://')
        pass "Database accessible: $db_info"
    fi

    if echo "$MONGO_CHECK" | grep -q "SERVER"; then
        server_ver=$(echo "$MONGO_CHECK" | grep "SERVER" | sed 's/SERVER://')
        pass "MongoDB server version: $server_ver"
    fi

    if echo "$MONGO_CHECK" | grep -q "NODES"; then
        nodes_info=$(echo "$MONGO_CHECK" | grep "NODES" | sed 's/NODES://')
        pass "Cluster: $nodes_info"
    fi
fi

# ── 6. Bootstrap MongoDB collections ────────────────────────
header "MongoDB Atlas — Collection Bootstrap"

if [[ -n "$ATLAS_URI" ]] && echo "$MONGO_CHECK" | grep -q "PING_OK"; then
    .venv/bin/python3 -m crewai_productfeature_planner.scripts.setup_mongodb 2>&1 && \
        pass "Collections and indexes verified" || \
        record_fail "Collection bootstrap failed"
else
    warn "Skipping collection bootstrap (MongoDB not reachable)"
fi

# ── 7. LLM provider reachability (UAT/PROD) ─────────────────
if [[ "$DEPLOY_ENV" == "uat" || "$DEPLOY_ENV" == "prod" ]]; then
    header "LLM Provider Reachability"

    if $has_openai; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: Bearer ${OPENAI_API_KEY}" \
            "https://api.openai.com/v1/models" 2>/dev/null || echo "000")
        if [[ "$HTTP_CODE" == "200" ]]; then
            pass "OpenAI API reachable (HTTP $HTTP_CODE)"
        else
            record_fail "OpenAI API returned HTTP $HTTP_CODE"
        fi
    fi

    if $has_gemini; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            "https://generativelanguage.googleapis.com/v1beta/models?key=${GOOGLE_API_KEY}" \
            2>/dev/null || echo "000")
        if [[ "$HTTP_CODE" == "200" ]]; then
            pass "Gemini API reachable (HTTP $HTTP_CODE)"
        else
            record_fail "Gemini API returned HTTP $HTTP_CODE"
        fi
    fi
fi

# ── 8. Atlassian integrations (UAT/PROD) ────────────────────
if [[ "$DEPLOY_ENV" == "uat" || "$DEPLOY_ENV" == "prod" ]]; then
    header "Atlassian Integrations"

    ATLAS_BASE="${ATLASSIAN_BASE_URL:-}"
    ATLAS_USER="${ATLASSIAN_USERNAME:-}"
    ATLAS_TOKEN="${ATLASSIAN_API_TOKEN:-}"

    if [[ -n "$ATLAS_BASE" && -n "$ATLAS_USER" && -n "$ATLAS_TOKEN" ]]; then
        AUTH_HEADER=$(echo -n "${ATLAS_USER}:${ATLAS_TOKEN}" | base64)

        # Confluence check
        CONF_KEY="${CONFLUENCE_SPACE_KEY:-}"
        if [[ -n "$CONF_KEY" ]]; then
            CONF_BASE=$(echo "$ATLAS_BASE" | sed 's|/$||')
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
                -H "Authorization: Basic $AUTH_HEADER" \
                -H "Accept: application/json" \
                "${CONF_BASE}/rest/api/space/${CONF_KEY}" 2>/dev/null || echo "000")
            if [[ "$HTTP_CODE" == "200" ]]; then
                pass "Confluence space '$CONF_KEY' accessible (HTTP $HTTP_CODE)"
            else
                record_warn "Confluence check returned HTTP $HTTP_CODE"
            fi
        else
            warn "CONFLUENCE_SPACE_KEY not set — skipping Confluence check"
        fi

        # Jira check
        JIRA_KEY="${JIRA_PROJECT_KEY:-}"
        if [[ -n "$JIRA_KEY" ]]; then
            JIRA_BASE=$(echo "$ATLAS_BASE" | sed 's|/$||')
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
                -H "Authorization: Basic $AUTH_HEADER" \
                -H "Accept: application/json" \
                "${JIRA_BASE}/rest/api/3/project/${JIRA_KEY}" 2>/dev/null || echo "000")
            if [[ "$HTTP_CODE" == "200" ]]; then
                pass "Jira project '$JIRA_KEY' accessible (HTTP $HTTP_CODE)"
            else
                record_warn "Jira check returned HTTP $HTTP_CODE"
            fi
        else
            warn "JIRA_PROJECT_KEY not set — skipping Jira check"
        fi
    else
        warn "Atlassian credentials incomplete — skipping integration checks"
    fi
fi

# ── 9. VS Code configuration (dev only) ─────────────────────
if [[ "$DEPLOY_ENV" == "dev" ]]; then
    header "VS Code Configuration"
    info ".vscode/settings.json → CODEX.md as Copilot instruction file"
    info ".github/copilot-instructions.md → references CODEX.md"
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
        pass "Created .vscode/extensions.json"
    else
        pass ".vscode/extensions.json exists"
    fi
fi

# ── 10. Summary ─────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════"

if [[ $FAILURES -gt 0 ]]; then
    echo -e "  ${RED}${BOLD}DEPLOYMENT CHECK FAILED${RESET}"
    echo -e "  ${RED}$FAILURES failure(s), $WARNINGS warning(s)${RESET}"
    echo ""
    echo "  Fix the issues above before deploying to $(echo "$DEPLOY_ENV" | tr '[:lower:]' '[:upper:]')."
    echo "══════════════════════════════════════════════════════════"
    exit 1
elif [[ $WARNINGS -gt 0 ]]; then
    echo -e "  ${YELLOW}${BOLD}DEPLOYMENT CHECK PASSED WITH WARNINGS${RESET}"
    echo -e "  ${YELLOW}$WARNINGS warning(s)${RESET}"
else
    echo -e "  ${GREEN}${BOLD}DEPLOYMENT CHECK PASSED${RESET}"
fi

echo ""
echo "  Environment: $(echo "$DEPLOY_ENV" | tr '[:lower:]' '[:upper:]')"
echo "  Database:    ${MONGODB_DB:-ideas} @ MongoDB Atlas"
if [[ -n "${ATLAS_DOMAIN:-}" ]]; then
    echo "  Cluster:     $ATLAS_DOMAIN"
fi
echo ""

if [[ "$DEPLOY_ENV" == "dev" ]]; then
    echo "  Next steps:"
    echo "    1. Start the server:  ./start_server.sh"
    echo "    2. Run tests:         .venv/bin/python -m pytest -x -q"
fi
if [[ "$DEPLOY_ENV" == "uat" ]]; then
    echo "  Next steps:"
    echo "    1. Start the server:  ./start_server.sh"
    echo "    2. Verify Slack webhooks are configured to the UAT URL"
fi
if [[ "$DEPLOY_ENV" == "prod" ]]; then
    echo "  Next steps:"
    echo "    1. Start with watchdog:  ./start_server_watchdog.sh"
    echo "    2. Monitor logs:         tail -f logs/crewai.log"
fi
echo ""
echo "══════════════════════════════════════════════════════════"
