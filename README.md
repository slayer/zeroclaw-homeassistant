# ZeroClaw Home Assistant Addon + Integration

Run [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw) AI agent runtime as a Home Assistant addon, with a custom integration for conversation, sensors, and service calls.

> **Note:** This addon uses binaries from the [slayer/zeroclaw](https://github.com/slayer/zeroclaw) fork, which adds `gateway.path_prefix` support required for Home Assistant ingress. See [slayer/zeroclaw#1](https://github.com/slayer/zeroclaw/pull/1) for details.

## Components

Both components are required:

- **Addon** (`zeroclaw_assistant/`) — Docker container that runs the ZeroClaw daemon (the AI runtime)
- **Integration** (`custom_components/zeroclaw/`) — Connects HA to the daemon, providing conversation agent, sensors, and services

The addon is the engine; the integration is how HA talks to it.

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
3. If the addon is running locally, setup completes automatically (the integration reads the addon's pre-seeded bearer token)
4. For remote installs, enter host, port, and the pairing code from the addon logs

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

**"Invalid pairing code"** (remote installs only)
- Pairing codes are single-use. Restart the addon to generate a new one
- Check the addon logs for the current code

**Integration setup doesn't auto-detect the addon**
- The addon must be running before adding the integration
- Auto-detection only works when the addon runs on the same HA instance
