DOMAIN = "zeroclaw"

PLATFORMS = ["sensor", "binary_sensor", "conversation"]

# Addon discovery
ADDON_SLUG = "zeroclaw_assistant"

# API endpoints
ENDPOINT_HEALTH = "/health"
ENDPOINT_STATUS = "/api/status"
ENDPOINT_WEBHOOK = "/webhook"
ENDPOINT_PAIR = "/pair"

# Defaults
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 42617
POLL_INTERVAL_SECONDS = 30

# Config keys (CONF_HOST and CONF_PORT come from homeassistant.const)
CONF_TOKEN = "token"
CONF_PAIRING_CODE = "pairing_code"

# Data keys
DATA_CLIENT = "client"
DATA_COORDINATOR = "coordinator"
