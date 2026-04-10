#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# sso_bootstrap.sh — One-time SSO application setup
#
# Usage:
#   ./scripts/sso_bootstrap.sh              # interactive (register new app)
#   ./scripts/sso_bootstrap.sh --env uat    # register with UAT + DEV URIs
#   ./scripts/sso_bootstrap.sh --env prod   # register with PROD + DEV URIs
#
# What it does:
#   1. Authenticates with the SSO server as SYS_ADMIN (handles 2FA)
#   2. Checks for existing "Idea Foundry" app, deletes if found
#   3. Registers "Idea Foundry" with ALL redirect_uris (DEV, UAT, PROD)
#      so the same client_id/secret works across environments
#   4. Saves client_id, client_secret, app_id to .env
#   5. Downloads the SSO RSA public key for local JWT verification
#   6. Registers a webhook subscription for event notifications
#   7. Validates the new client_id is accepted
#
# Prerequisites:
#   - jq & python3 available
#   - A SYS_ADMIN account on the SSO server
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# ── Colour helpers ──────────────────────────────────────────
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

die() { echo -e "\n${RED}Error: $1${RESET}" >&2; exit 1; }

# ── Safe .env updater (Python — handles special chars) ──────
update_env_var() {
    local var_name="$1"
    local var_value="$2"
    python3 -c "
import re, sys
name, value = sys.argv[1], sys.argv[2]
with open('.env', 'r') as f:
    content = f.read()
pattern = rf'^{re.escape(name)}=.*$'
replacement = f'{name}={value}'
new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
if count == 0:
    new_content += f'\n{name}={value}\n'
with open('.env', 'w') as f:
    f.write(new_content)
" "$var_name" "$var_value"
}

# ── Parse args ──────────────────────────────────────────────
TARGET_ENV=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env) TARGET_ENV="${2:-}"; shift 2 ;;
        *)     shift ;;
    esac
done

# ── Check dependencies ─────────────────────────────────────
command -v curl    >/dev/null 2>&1 || die "curl is required"
command -v jq      >/dev/null 2>&1 || die "jq is required (brew install jq)"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

# ── Load .env ───────────────────────────────────────────────
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

SSO_BASE_URL="${SSO_BASE_URL:-https://oldfangled-caylee-implosively.ngrok-free.dev}"

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  SSO Application Bootstrap"
echo "  SSO Server: ${SSO_BASE_URL}"
echo "══════════════════════════════════════════════════════════"

# ── 1. Health check ─────────────────────────────────────────
header "SSO Server Health Check"
HEALTH=$(curl -s -H "ngrok-skip-browser-warning: true" \
    "${SSO_BASE_URL}/sso/health" 2>&1) \
    || die "Cannot reach SSO server at ${SSO_BASE_URL}"
STATUS=$(echo "$HEALTH" | jq -r '.status // empty' 2>/dev/null)
if [[ "$STATUS" == "ok" ]]; then
    pass "SSO server is healthy"
else
    die "SSO server health check failed: $HEALTH"
fi

# ── 2. Authenticate as SYS_ADMIN ───────────────────────────
header "Admin Authentication"
echo -n "  SSO admin email: "
read -r ADMIN_EMAIL
echo -n "  SSO admin password: "
read -rs ADMIN_PASSWORD
echo ""

LOGIN_BODY=$(jq -n --arg e "$ADMIN_EMAIL" --arg p "$ADMIN_PASSWORD" \
    '{email:$e, password:$p}')

LOGIN_RESP=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "ngrok-skip-browser-warning: true" \
    "${SSO_BASE_URL}/sso/auth/login" \
    -d "$LOGIN_BODY" 2>&1)

TWO_FA=$(echo "$LOGIN_RESP" | jq -r '.two_factor_required // empty' 2>/dev/null)
ACCESS_TOKEN=$(echo "$LOGIN_RESP" | jq -r '.access_token // empty' 2>/dev/null)

if [[ "$TWO_FA" == "true" ]]; then
    LOGIN_TOKEN=$(echo "$LOGIN_RESP" | jq -r '.login_token // empty' 2>/dev/null)
    info "2FA code sent to ${ADMIN_EMAIL}"
    echo -n "  Enter 2FA code: "
    read -r TFA_CODE

    TFA_BODY=$(jq -n --arg e "$ADMIN_EMAIL" --arg t "$LOGIN_TOKEN" \
        --arg c "$TFA_CODE" '{email:$e, login_token:$t, code:$c}')

    TFA_RESP=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -H "ngrok-skip-browser-warning: true" \
        "${SSO_BASE_URL}/sso/auth/login/verify-2fa" \
        -d "$TFA_BODY" 2>&1)

    ACCESS_TOKEN=$(echo "$TFA_RESP" | jq -r '.access_token // empty' 2>/dev/null)
    [[ -z "$ACCESS_TOKEN" ]] && die "2FA failed: $(echo "$TFA_RESP" | jq -r '.detail.message // .detail // .' 2>/dev/null)"
    pass "Authenticated with 2FA"
elif [[ -n "$ACCESS_TOKEN" ]]; then
    pass "Authenticated (no 2FA)"
else
    die "Login failed: $(echo "$LOGIN_RESP" | jq -r '.detail.message // .detail // .' 2>/dev/null)"
fi

AUTH_HEADER="Authorization: Bearer ${ACCESS_TOKEN}"

# ── 3. Collect ALL redirect_uris (DEV + UAT + PROD) ────────
header "Redirect URIs"

REDIRECT_URIS=()

# DEV URI
NGROK_DOM="${NGROK_DOMAIN:-}"
if [[ -n "$NGROK_DOM" ]]; then
    [[ "$NGROK_DOM" =~ ^https?:// ]] || NGROK_DOM="https://${NGROK_DOM}"
    REDIRECT_URIS+=("${NGROK_DOM}/auth/sso/callback")
    info "DEV (ngrok): ${NGROK_DOM}/auth/sso/callback"
fi
PORT="${PORT:-8000}"
REDIRECT_URIS+=("http://localhost:${PORT}/auth/sso/callback")
info "DEV (local):  http://localhost:${PORT}/auth/sso/callback"

# UAT URI
UAT_DOM="${DOMAIN_NAME_UAT:-}"
if [[ -n "$UAT_DOM" ]]; then
    [[ "$UAT_DOM" =~ ^https?:// ]] || UAT_DOM="https://${UAT_DOM}"
    REDIRECT_URIS+=("${UAT_DOM}/auth/sso/callback")
    info "UAT:          ${UAT_DOM}/auth/sso/callback"
fi

# PROD URI
PROD_DOM="${DOMAIN_NAME_PROD:-}"
if [[ -n "$PROD_DOM" ]]; then
    [[ "$PROD_DOM" =~ ^https?:// ]] || PROD_DOM="https://${PROD_DOM}"
    REDIRECT_URIS+=("${PROD_DOM}/auth/sso/callback")
    info "PROD:         ${PROD_DOM}/auth/sso/callback"
fi

# Build JSON array of redirect_uris
URIS_JSON=$(printf '%s\n' "${REDIRECT_URIS[@]}" | jq -R . | jq -s .)
info "Total redirect_uris: ${#REDIRECT_URIS[@]}"

# ── 4. Check for existing app with same name ────────────────
header "Application Check"

APPS_RESP=$(curl -s \
    -H "$AUTH_HEADER" \
    -H "ngrok-skip-browser-warning: true" \
    "${SSO_BASE_URL}/sso/apps" 2>&1)

EXISTING_APP_ID=""
if echo "$APPS_RESP" | jq -e 'type == "array"' >/dev/null 2>&1; then
    EXISTING_APP_ID=$(echo "$APPS_RESP" | jq -r \
        '[.[] | select(.name == "Idea Foundry")] | .[0] | .app_id // .id // empty' 2>/dev/null)
fi

if [[ -n "$EXISTING_APP_ID" ]]; then
    EXISTING_CID=$(echo "$APPS_RESP" | jq -r \
        --arg aid "$EXISTING_APP_ID" \
        '[.[] | select(.app_id == $aid or .id == $aid)] | .[0] | .client_id // empty' 2>/dev/null)
    info "Found existing 'Idea Foundry' app:"
    info "  app_id:    ${EXISTING_APP_ID}"
    info "  client_id: ${EXISTING_CID:-unknown}"

    # Check if we already have the client_secret for this app
    HAVE_SECRET=false
    if [[ -n "${SSO_CLIENT_SECRET:-}" && "${SSO_CLIENT_ID:-}" == "$EXISTING_CID" ]]; then
        HAVE_SECRET=true
    fi

    if $HAVE_SECRET; then
        echo -n "  Credentials found in .env. Re-register anyway? [y/N] "
        read -r CONFIRM
        if [[ "$CONFIRM" =~ ^[Yy] ]]; then
            DEL_RESP=$(curl -s -X DELETE \
                -H "$AUTH_HEADER" \
                -H "ngrok-skip-browser-warning: true" \
                "${SSO_BASE_URL}/sso/apps/${EXISTING_APP_ID}" 2>&1)
            pass "Deleted old app"
            EXISTING_APP_ID=""
        else
            # Keep existing — just update app_id in .env
            update_env_var "SSO_EXPECTED_APP_ID" "$EXISTING_APP_ID"
            pass "Keeping existing app — credentials preserved"
        fi
    else
        warn "client_secret is missing from .env — must delete and re-register"
        echo -n "  Delete and re-register to get fresh credentials? [Y/n] "
        read -r CONFIRM
        if [[ ! "$CONFIRM" =~ ^[Nn] ]]; then
            DEL_RESP=$(curl -s -X DELETE \
                -H "$AUTH_HEADER" \
                -H "ngrok-skip-browser-warning: true" \
                "${SSO_BASE_URL}/sso/apps/${EXISTING_APP_ID}" 2>&1)
            DEL_STATUS=$(echo "$DEL_RESP" | jq -r '.status // .detail // empty' 2>/dev/null)
            pass "Deleted old app (${DEL_STATUS:-ok})"
            EXISTING_APP_ID=""
        else
            # Keep but warn — no secret means OAuth token exchange will fail
            update_env_var "SSO_CLIENT_ID" "$EXISTING_CID"
            update_env_var "SSO_EXPECTED_APP_ID" "$EXISTING_APP_ID"
            pass "Updated SSO_CLIENT_ID=${EXISTING_CID}"
            fail "SSO_CLIENT_SECRET is empty — OAuth token exchange will fail!"
            fail "Re-run this script and choose Y to get fresh credentials."
        fi
    fi
else
    info "No existing 'Idea Foundry' app found"
fi

# ── 5. Register the app (SYS_ADMIN = auto-approved) ────────
header "App Registration"

# Only register if we deleted the old one or it didn't exist
NEED_REGISTER=true
if [[ -n "$EXISTING_APP_ID" ]]; then
    NEED_REGISTER=false
fi

if $NEED_REGISTER; then
    REG_BODY=$(jq -n \
        --arg name "Idea Foundry" \
        --argjson uris "$URIS_JSON" \
        '{name:$name, redirect_uris:$uris, scopes:["openid","profile","email"]}')

    info "Registering with ${#REDIRECT_URIS[@]} redirect_uris …"
    info "POST /sso/apps/register"
    REG_RESP=$(curl -s -X POST \
        -H "$AUTH_HEADER" \
        -H "Content-Type: application/json" \
        -H "ngrok-skip-browser-warning: true" \
        "${SSO_BASE_URL}/sso/apps/register" \
        -d "$REG_BODY" 2>&1)

    NEW_CID=$(echo "$REG_RESP" | jq -r '.client_id // empty' 2>/dev/null)
    NEW_SECRET=$(echo "$REG_RESP" | jq -r '.client_secret // empty' 2>/dev/null)
    NEW_AID=$(echo "$REG_RESP" | jq -r '.app_id // empty' 2>/dev/null)

    if [[ -n "$NEW_CID" && -n "$NEW_SECRET" ]]; then
        pass "Registered!"
        info "  app_id:        ${NEW_AID}"
        info "  client_id:     ${NEW_CID}"
        info "  client_secret: ${NEW_SECRET:0:12}…"
        echo ""

        update_env_var "SSO_CLIENT_ID" "$NEW_CID"
        update_env_var "SSO_CLIENT_SECRET" "$NEW_SECRET"
        update_env_var "SSO_EXPECTED_APP_ID" "$NEW_AID"

        pass "Saved credentials to .env"
    else
        echo ""
        fail "Registration response:"
        echo "$REG_RESP" | jq '.' 2>/dev/null || echo "  $REG_RESP"
        echo ""
        die "POST /sso/apps/register did not return client_id + client_secret"
    fi
fi

# ── 6. Download SSO public key ──────────────────────────────
header "RSA Public Key"
PK_RESP=$(curl -s \
    -H "ngrok-skip-browser-warning: true" \
    "${SSO_BASE_URL}/sso/oauth/public-key" 2>&1)

PK_PEM=$(echo "$PK_RESP" | jq -r '.public_key_pem // empty' 2>/dev/null)
if [[ -n "$PK_PEM" ]]; then
    echo "$PK_PEM" > sso_public_key.pem
    update_env_var "SSO_JWT_PUBLIC_KEY_PATH" "sso_public_key.pem"
    pass "Saved RSA public key → sso_public_key.pem"
    pass "Updated SSO_JWT_PUBLIC_KEY_PATH in .env"
else
    warn "Could not download public key: ${PK_RESP}"
fi

# ── 7. Register webhook subscription ───────────────────────
header "Webhook Subscription"

# Determine our webhook URL based on the target environment
DEPLOY="${TARGET_ENV:-${SERVER_ENV:-DEV}}"
DEPLOY=$(echo "$DEPLOY" | tr '[:lower:]' '[:upper:]')

case "$DEPLOY" in
    UAT)
        WH_DOMAIN="${DOMAIN_NAME_UAT:-}"
        [[ -n "$WH_DOMAIN" ]] && { [[ "$WH_DOMAIN" =~ ^https?:// ]] || WH_DOMAIN="https://${WH_DOMAIN}"; }
        ;;
    PROD|PRODUCTION)
        WH_DOMAIN="${DOMAIN_NAME_PROD:-}"
        [[ -n "$WH_DOMAIN" ]] && { [[ "$WH_DOMAIN" =~ ^https?:// ]] || WH_DOMAIN="https://${WH_DOMAIN}"; }
        DEPLOY="PROD"
        ;;
    *)
        WH_DOMAIN="${NGROK_DOMAIN:-}"
        [[ -n "$WH_DOMAIN" ]] && { [[ "$WH_DOMAIN" =~ ^https?:// ]] || WH_DOMAIN="https://${WH_DOMAIN}"; }
        DEPLOY="DEV"
        ;;
esac

if [[ -z "$WH_DOMAIN" ]]; then
    WH_DOMAIN="http://localhost:${PORT:-8000}"
fi

WEBHOOK_URL="${WH_DOMAIN}/sso/webhooks/events"
info "Environment:   ${DEPLOY}"
info "Webhook URL:   ${WEBHOOK_URL}"

WH_BODY=$(jq -n \
    --arg url "$WEBHOOK_URL" \
    '{url:$url, events:["user.created","user.updated","user.deleted","login.success","login.failed","token.revoked"]}')

WH_RESP=$(curl -s -X POST \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -H "ngrok-skip-browser-warning: true" \
    "${SSO_BASE_URL}/sso/webhooks/register" \
    -d "$WH_BODY" 2>&1)

WH_SECRET=$(echo "$WH_RESP" | jq -r '.secret // .webhook_secret // empty' 2>/dev/null)
WH_ID=$(echo "$WH_RESP" | jq -r '.webhook_id // .id // empty' 2>/dev/null)

if [[ -n "$WH_SECRET" ]]; then
    update_env_var "SSO_WEBHOOK_SECRET" "$WH_SECRET"
    pass "Webhook registered (id: ${WH_ID:-n/a})"
    pass "Saved SSO_WEBHOOK_SECRET to .env"
elif [[ -n "$WH_ID" ]]; then
    pass "Webhook registered (id: ${WH_ID})"
    warn "No secret returned — SSO_WEBHOOK_SECRET unchanged"
else
    warn "Webhook registration response: $(echo "$WH_RESP" | jq -r '.detail // .' 2>/dev/null)"
    warn "Manually register at: ${SSO_BASE_URL}/sso/docs → POST /webhooks/register"
fi

# ── 8. Verify configuration ────────────────────────────────
header "Configuration Verification"

# Re-source .env to pick up saves
set -a; source .env; set +a

ALL_OK=true
for var in SSO_BASE_URL SSO_CLIENT_ID SSO_CLIENT_SECRET SSO_JWT_PUBLIC_KEY_PATH SSO_ISSUER SSO_EXPECTED_APP_ID; do
    val="${!var:-}"
    if [[ -n "$val" ]]; then
        if [[ "$var" == *SECRET* ]]; then
            pass "${var} = ${val:0:8}…"
        else
            pass "${var} = ${val}"
        fi
    else
        fail "${var} is empty"
        ALL_OK=false
    fi
done

[[ -f sso_public_key.pem ]] \
    && pass "sso_public_key.pem exists ($(wc -c < sso_public_key.pem | tr -d ' ') bytes)" \
    || warn "sso_public_key.pem not found"

# ── 9. Client-ID acceptance test ────────────────────────────
header "Client ID Acceptance Test"
CID="${SSO_CLIENT_ID:-}"
if [[ -n "$CID" ]]; then
    TEST_BODY=$(jq -n --arg e "healthcheck@example.com" --arg p "x" \
        --arg c "$CID" '{email:$e, password:$p, client_id:$c}')

    TEST_RESP=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -H "ngrok-skip-browser-warning: true" \
        "${SSO_BASE_URL}/sso/auth/login" \
        -d "$TEST_BODY" 2>&1)

    ERR=$(echo "$TEST_RESP" | jq -r '.detail.code // empty' 2>/dev/null)
    case "$ERR" in
        AUTH_1001) pass "client_id accepted (AUTH_1001 = bad creds, expected)" ;;
        AUTH_2009) fail "client_id rejected — app not approved (AUTH_2009)"; ALL_OK=false ;;
        *)        warn "Unexpected: $ERR — $(echo "$TEST_RESP" | jq -r '.detail.message // .' 2>/dev/null)" ;;
    esac
else
    warn "SSO_CLIENT_ID is empty — skipping"
fi

# ── Summary ─────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════"
if $ALL_OK; then
    echo -e "  ${GREEN}${BOLD}SSO BOOTSTRAP COMPLETE${RESET}"
    echo ""
    echo "  Credentials saved to .env — same client works across all environments."
    echo ""
    echo "  Next steps:"
    echo "    1. Restart the server:  ./start_server.sh"
    echo "    2. Test login:          curl -X POST http://localhost:8000/auth/sso/login \\"
    echo "                              -H 'Content-Type: application/json' \\"
    echo "                              -d '{\"email\":\"…\",\"password\":\"…\"}'"
    echo ""
    echo "  For UAT/PROD — use same .env credentials, just set SERVER_ENV:"
    echo "    SERVER_ENV=UAT  ./start_server.sh"
    echo "    SERVER_ENV=PROD ./start_server.sh"
else
    echo -e "  ${YELLOW}${BOLD}SSO BOOTSTRAP INCOMPLETE${RESET}"
    echo ""
    echo "  Re-run this script to fix missing items."
fi
echo ""
echo "══════════════════════════════════════════════════════════"

# ── Logout ──────────────────────────────────────────────────
curl -s -X POST \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -H "ngrok-skip-browser-warning: true" \
    "${SSO_BASE_URL}/sso/auth/logout" >/dev/null 2>&1 || true
