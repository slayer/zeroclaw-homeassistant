# ZeroClaw Home Assistant Addon + Integration

Run [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw) AI agent runtime as a Home Assistant addon, with a custom integration for conversation, sensors, and service calls.

## Components

- **Addon** (`zeroclaw_assistant/`) — Docker container running the ZeroClaw binary
- **Integration** (`custom_components/zeroclaw/`) — HA custom integration providing conversation agent, sensors, and services

## Installation

### 1. Install the Addon

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**
2. Click the **⋮** menu (top right) → **Repositories**
3. Add this repository URL:
   ```
   https://github.com/slayer/zeroclaw-homeassistant
   ```
4. Find **ZeroClaw Assistant** in the store and click **Install**
5. Go to the addon **Configuration** tab and set:
   - **llm_provider** — your LLM provider (e.g. `openrouter`, `anthropic`, `openai`, `ollama`)
   - **api_key** — your API key for the provider
   - **default_model** — (optional) model identifier (e.g. `anthropic/claude-sonnet-4-20250514`)
6. Click **Start**
7. Check the **Log** tab — look for the **pairing code** (you'll need it in the next step)

### 2. Install the Integration

#### Option A: HACS (recommended)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**
2. Add this repository URL with category **Integration**:
   ```
   https://github.com/slayer/zeroclaw-homeassistant
   ```
3. Search for **ZeroClaw Assistant** and install it
4. Restart Home Assistant

#### Option B: Manual

1. Copy the `custom_components/zeroclaw/` folder to your HA `config/custom_components/` directory
2. Restart Home Assistant

### 3. Configure the Integration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **ZeroClaw**
3. Enter:
   - **Host** — `127.0.0.1` (if addon is running locally)
   - **Port** — `42617` (default)
   - **Pairing Code** — the code from the addon logs
4. Click **Submit**

## What You Get

### Conversation Agent

ZeroClaw registers as a conversation agent in HA Assist. To use it:

1. Go to **Settings → Voice assistants**
2. Create or edit an assistant
3. Set **Conversation agent** to **ZeroClaw**

Now you can talk to ZeroClaw via the Assist UI, voice, or automations.

### Entities

| Entity | Type | Description |
|--------|------|-------------|
| ZeroClaw Connected | Binary Sensor | Gateway connectivity status |
| ZeroClaw Status | Sensor | Gateway status (ok/error), with uptime and component info |
| ZeroClaw Active Model | Sensor | Current LLM model name and provider |

### Services

**`zeroclaw.send_message`** — Send a message and get a response.

```yaml
service: zeroclaw.send_message
data:
  message: "What is the weather like today?"
```

Returns `response` (LLM answer) and `model` (model used).

## Addon Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `llm_provider` | `openrouter` | LLM provider (`openrouter`, `anthropic`, `openai`, `groq`, `mistral`, `deepseek`, `together`, `fireworks`, `ollama`, `custom`) |
| `api_key` | — | API key for the provider |
| `default_model` | — | Model identifier (empty = provider default) |
| `gateway_port` | `42617` | Gateway HTTP port |
| `env_vars` | `[]` | Additional environment variables (list of `name`/`value` pairs) |

## Supported Architectures

- amd64
- aarch64 (Raspberry Pi 4/5)
- armv7 (Raspberry Pi 3)

## Troubleshooting

**"Cannot connect to ZeroClaw gateway"**
- Check the addon is running (Settings → Add-ons → ZeroClaw Assistant)
- Verify the port matches between addon config and integration setup

**"Invalid pairing code"**
- Pairing codes are single-use. Restart the addon to generate a new one
- Check the addon logs for the current code

**Integration becomes unavailable after addon restart**
- ZeroClaw may regenerate tokens on restart. Delete and re-add the integration with the new pairing code
