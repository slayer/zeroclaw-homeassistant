# ZeroClaw Home Assistant Addon

Run [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw) AI agent runtime as a Home Assistant addon.

> **Integration required:** To connect Home Assistant to this addon, install the [ZeroClaw integration](https://github.com/slayer/zeroclaw-homeassistant-integration) via HACS or manually.

> **Note:** This addon uses binaries from the [slayer/zeroclaw](https://github.com/slayer/zeroclaw) fork, which adds `gateway.path_prefix` support required for Home Assistant ingress. See [slayer/zeroclaw#1](https://github.com/slayer/zeroclaw/pull/1) for details.

## Installation

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
7. Install the [ZeroClaw integration](https://github.com/slayer/zeroclaw-homeassistant-integration) to connect HA to the addon

## Configuration Options

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

**Addon won't start**
- Check the addon logs for error messages
- Verify your `api_key` is correct for the selected `llm_provider`

**Cannot connect from integration**
- Make sure the addon is running (Settings → Add-ons → ZeroClaw Assistant)
- Verify the port matches between addon config and integration setup
