# Ansible Role `ctlabs_claude_code`

## Ansible Tags

- `ctlabs_claude_code`
- `ctlabs_claude_code.precheck`
- `ctlabs_claude_code.package`
- `ctlabs_claude_code.config`
- `ctlabs_claude_code.service`

## Prechecks

- OS: debian12, kali2025, kali2026, parrot6, parrot7, centos9

## Description

Installs [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) via npm (`@anthropic-ai/claude-code`). Sets up:

- Node.js 22.x via NodeSource (Debian/RedHat)
- `claude` system user
- Claude Code config at `~/.claude/settings.json`

Both provider configuration and OTLP telemetry are **opt-in** — disabled by default. Enable via local facts.

## Provider Configuration

Claude Code supports multiple API providers. Select exactly one via `provider.active` in local facts.

| Provider | Env vars set | Local fact path |
|---|---|---|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | `ctg_facts.ctlabs_claude_code.provider.anthropic.api_key` |
| `openrouter` | `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_SKIP_FAST_MODE_ORG_CHECK=1` | `ctg_facts.ctlabs_claude_code.provider.openrouter.{api_key,base_url}` |
| `vertexai` | `ANTHROPIC_API_KEY=""`, `CLAUDE_CODE_USE_VERTEX=1`, `ANTHROPIC_VERTEX_PROJECT_ID`, `CLOUD_ML_REGION`, `GCE_METADATA_HOST` | `ctg_facts.ctlabs_claude_code.provider.vertexai.{project_id,region}` |

The `vertexai` provider assumes Application Default Credentials (ADC) are already configured on the host (e.g. via `ctlabs_gcloud`).

## OTLP Telemetry

Claude Code can emit OpenTelemetry metrics to a Prometheus OTLP receiver. **Opt-in** — disabled by default.

Configured via `ctg_facts.ctlabs_claude_code.otlp` (merged over `ctlabs_claude_code.defaults.config.otlp`):

| Key | Default | Description |
|---|---|---|
| `enabled` | `false` | Enable OTLP metric export |
| `endpoint` | `http://prometheus.ctlabs.internal:9090/v1/metrics` | OTLP receiver URL |
| `resource_attrs` | `user.email=<ansible_user>` | `OTEL_RESOURCE_ATTRIBUTES` value |

## Preferences

Claude Code UI/model preferences are configured via `ctg_facts.ctlabs_claude_code.preferences` (merged over `ctlabs_claude_code.defaults.config.preferences`):

| Key | Default | Description |
|---|---|---|
| `model` | `claude-sonnet-4-6` | Default model |
| `theme` | `dark` | UI theme |
| `always_thinking` | `false` | Enable extended thinking |
| `fast_mode` | `true` | Enable fast mode |
| `fallback_model` | `["haiku"]` | Fallback model list |
| `gce_metadata_host` | `""` | `GCE_METADATA_HOST` override (vertexai only) |

## Local Facts Example

`/etc/ansible/facts.d/ctlabs_claude_code.fact`:

```json
{
  "provider": {
    "active": "vertexai",
    "vertexai": {
      "project_id": "my-gcp-project",
      "region": "us-east5"
    }
  },
  "otlp": {
    "enabled": true,
    "endpoint": "https://prometheus.example.com/api/v1/otlp",
    "resource_attrs": "user.email=user@example.com"
  },
  "preferences": {
    "model": "claude-sonnet-4-6",
    "theme": "dark",
    "always_thinking": false,
    "fast_mode": true,
    "fallback_model": ["haiku"],
    "gce_metadata_host": "127.0.0.1:1"
  }
}
```

## Tests

```sh
pytest -sv roles/ctlabs_claude_code/tests
```

