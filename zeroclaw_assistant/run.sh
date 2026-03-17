#!/usr/bin/with-contenv bashio
# Reads HA addon options, patches config.toml (preserving user edits), starts zeroclaw daemon.

set -euo pipefail

CONFIG_DIR="/config/zeroclaw"
CONFIG_FILE="${CONFIG_DIR}/config.toml"
TOKEN_FILE="${CONFIG_DIR}/.bearer_token"
OPTIONS_FILE="/data/options.json"

# --- Read addon options ---
LLM_PROVIDER=$(jq -r '.llm_provider' "${OPTIONS_FILE}")
API_KEY=$(jq -r '.api_key' "${OPTIONS_FILE}")
DEFAULT_MODEL=$(jq -r '.default_model // ""' "${OPTIONS_FILE}")
GATEWAY_PORT=$(jq -r '.gateway_port // 42617' "${OPTIONS_FILE}")

# --- Apply extra env vars ---
ENV_COUNT=$(jq '.env_vars | length' "${OPTIONS_FILE}")
for i in $(seq 0 $((ENV_COUNT - 1))); do
  NAME=$(jq -r ".env_vars[$i].name" "${OPTIONS_FILE}")
  VALUE=$(jq -r ".env_vars[$i].value" "${OPTIONS_FILE}")
  export "${NAME}=${VALUE}"
done

# --- Pre-seed bearer token (reuse across restarts) ---
mkdir -p "${CONFIG_DIR}"
if [ -f "${TOKEN_FILE}" ]; then
  BEARER_TOKEN=$(cat "${TOKEN_FILE}")
else
  BEARER_TOKEN="zc_$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  printf '%s' "${BEARER_TOKEN}" > "${TOKEN_FILE}"
  chmod 600 "${TOKEN_FILE}"
fi

# --- Generate or patch config.toml ---
# On first start: generate full config.
# On subsequent starts: only update addon-managed fields, preserve user edits.
if [ ! -f "${CONFIG_FILE}" ]; then
  bashio::log.info "First start — generating config.toml"
  cat > "${CONFIG_FILE}" <<EOF
# ZeroClaw HA addon config.
# Lines between "# HA-MANAGED" markers are updated on each restart.
# Everything else is preserved — feel free to add your own settings.

# HA-MANAGED-START provider
default_provider = "${LLM_PROVIDER}"
api_key = "${API_KEY}"
EOF
  if [ -n "${DEFAULT_MODEL}" ]; then
    echo "default_model = \"${DEFAULT_MODEL}\"" >> "${CONFIG_FILE}"
  fi
  cat >> "${CONFIG_FILE}" <<EOF
# HA-MANAGED-END provider

[gateway]
host = "0.0.0.0"
port = ${GATEWAY_PORT}
allow_public_bind = true
require_pairing = false
webhook_tools = true
# HA-MANAGED-START gateway-tokens
paired_tokens = ["${BEARER_TOKEN}"]
# HA-MANAGED-END gateway-tokens

# HA-MANAGED-START mcp
# HA-MANAGED-END mcp
EOF
else
  bashio::log.info "Patching existing config.toml (preserving user edits)"

  # Helper: replace content between HA-MANAGED markers
  patch_section() {
    local section="$1"
    local content="$2"
    local start_marker="# HA-MANAGED-START ${section}"
    local end_marker="# HA-MANAGED-END ${section}"

    if grep -q "${start_marker}" "${CONFIG_FILE}"; then
      # Replace content between markers (inclusive of markers)
      awk -v start="${start_marker}" -v end="${end_marker}" -v new="${content}" '
        $0 == start { print start; print new; skip=1; next }
        skip && $0 == end { print end; skip=0; next }
        !skip { print }
      ' "${CONFIG_FILE}" > "${CONFIG_FILE}.tmp"
      mv "${CONFIG_FILE}.tmp" "${CONFIG_FILE}"
    fi
  }

  # Patch provider settings
  PROVIDER_BLOCK="default_provider = \"${LLM_PROVIDER}\"
api_key = \"${API_KEY}\""
  if [ -n "${DEFAULT_MODEL}" ]; then
    PROVIDER_BLOCK="${PROVIDER_BLOCK}
default_model = \"${DEFAULT_MODEL}\""
  fi
  patch_section "provider" "${PROVIDER_BLOCK}"

  # Patch bearer token
  patch_section "gateway-tokens" "paired_tokens = [\"${BEARER_TOKEN}\"]"
fi

# --- Auto-detect HA MCP server (retry up to 60s for HA to finish starting) ---
MCP_BLOCK=""
if [ -n "${SUPERVISOR_TOKEN:-}" ]; then
  MCP_CHECK="000"
  for attempt in $(seq 1 12); do
    MCP_CHECK=$(curl -s -o /dev/null -w "%{http_code}" \
      -X POST "http://supervisor/core/api/mcp" \
      -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
      -H "Content-Type: application/json" \
      -H "Accept: application/json" \
      -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"zeroclaw","version":"0.1"}}}' \
      2>/dev/null || echo "000")
    if [ "${MCP_CHECK}" = "200" ]; then
      break
    fi
    if [ "${attempt}" -lt 12 ]; then
      bashio::log.info "Waiting for HA MCP server (attempt ${attempt}/12, HTTP ${MCP_CHECK})..."
      sleep 5
    fi
  done
  if [ "${MCP_CHECK}" = "200" ]; then
    bashio::log.info "HA MCP server detected — enabling home control tools"
    MCP_BLOCK="[mcp]
enabled = true

[[mcp.servers]]
name = \"home-assistant\"
transport = \"http\"
url = \"http://supervisor/core/api/mcp\"
headers = { \"Authorization\" = \"Bearer ${SUPERVISOR_TOKEN}\" }"
  else
    bashio::log.info "HA MCP server not found (HTTP ${MCP_CHECK}) — skipping MCP config"
  fi
fi

# Patch or append MCP section
if grep -q "# HA-MANAGED-START mcp" "${CONFIG_FILE}"; then
  # Use the patch helper (re-declare for this scope since we might have skipped the else branch)
  start_marker="# HA-MANAGED-START mcp"
  end_marker="# HA-MANAGED-END mcp"
  awk -v start="${start_marker}" -v end="${end_marker}" -v new="${MCP_BLOCK}" '
    $0 == start { print start; if (new != "") print new; skip=1; next }
    skip && $0 == end { print end; skip=0; next }
    !skip { print }
  ' "${CONFIG_FILE}" > "${CONFIG_FILE}.tmp"
  mv "${CONFIG_FILE}.tmp" "${CONFIG_FILE}"
elif [ -n "${MCP_BLOCK}" ]; then
  # No markers yet — append MCP section
  printf '\n# HA-MANAGED-START mcp\n%s\n# HA-MANAGED-END mcp\n' "${MCP_BLOCK}" >> "${CONFIG_FILE}"
fi

chmod 600 "${CONFIG_FILE}"

bashio::log.info "Starting ZeroClaw daemon (provider=${LLM_PROVIDER}, port=${GATEWAY_PORT})"

# --- Start ZeroClaw ---
exec zeroclaw daemon --config-dir "${CONFIG_DIR}"
