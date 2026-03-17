#!/usr/bin/with-contenv bashio
# Reads HA addon options, seeds config.toml on first start, starts zeroclaw daemon.
# Provider/model/api_key are passed via env vars (ZeroClaw applies them as overrides).
# config.toml is only generated once — user edits are preserved across restarts.

set -euo pipefail

CONFIG_DIR="/config/zeroclaw"
CONFIG_FILE="${CONFIG_DIR}/config.toml"
TOKEN_FILE="${CONFIG_DIR}/.bearer_token"
OPTIONS_FILE="/data/options.json"

# --- Read addon options → export as env vars (ZeroClaw applies these on top of config.toml) ---
export ZEROCLAW_PROVIDER=$(jq -r '.llm_provider' "${OPTIONS_FILE}")
export ZEROCLAW_API_KEY=$(jq -r '.api_key' "${OPTIONS_FILE}")
export ZEROCLAW_MODEL=$(jq -r '.default_model // ""' "${OPTIONS_FILE}")
GATEWAY_PORT=$(jq -r '.gateway_port // 42617' "${OPTIONS_FILE}")

# --- Apply extra env vars from addon options ---
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

# --- Generate config.toml on first start only ---
if [ ! -f "${CONFIG_FILE}" ]; then
  bashio::log.info "First start — generating config.toml"
  cat > "${CONFIG_FILE}" <<EOF
# ZeroClaw HA addon config.
# Provider, model, and API key are managed via addon options (env var overrides).
# Edit this file freely — it is NOT overwritten on restart.

[gateway]
host = "0.0.0.0"
port = ${GATEWAY_PORT}
allow_public_bind = true
require_pairing = false
paired_tokens = ["${BEARER_TOKEN}"]
webhook_tools = true
EOF
  chmod 600 "${CONFIG_FILE}"
fi

# --- Ensure bearer token is in paired_tokens (even if user edited config) ---
if ! grep -q "${BEARER_TOKEN}" "${CONFIG_FILE}" 2>/dev/null; then
  sed -i "s|paired_tokens = \[.*\]|paired_tokens = [\"${BEARER_TOKEN}\"]|" "${CONFIG_FILE}"
fi

# --- Auto-detect HA MCP server (retry up to 60s for HA to finish starting) ---
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
    # Remove old MCP section if present, then append fresh one
    # (SUPERVISOR_TOKEN changes on each addon rebuild)
    sed -i '/^\[mcp\]/,/^$/d' "${CONFIG_FILE}"
    sed -i '/^\[\[mcp\.servers\]\]/,/^$/d' "${CONFIG_FILE}"
    cat >> "${CONFIG_FILE}" <<MCPEOF

[mcp]
enabled = true

[[mcp.servers]]
name = "home-assistant"
transport = "http"
url = "http://supervisor/core/api/mcp"
headers = { "Authorization" = "Bearer ${SUPERVISOR_TOKEN}" }
MCPEOF
  else
    bashio::log.info "HA MCP server not found (HTTP ${MCP_CHECK}) — skipping MCP config"
  fi
fi

bashio::log.info "Starting ZeroClaw daemon (provider=${ZEROCLAW_PROVIDER}, port=${GATEWAY_PORT})"

# --- Start ZeroClaw ---
exec zeroclaw daemon --config-dir "${CONFIG_DIR}"
