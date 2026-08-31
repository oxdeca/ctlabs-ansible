# Ansible Role `ctlabs_claude_code`

## Ansible Tags

- `ctlabs_claude_code`
- `ctlabs_claude_code.precheck`
- `ctlabs_claude_code.package`
- `ctlabs_claude_code.config`

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
| `vertexai` | `ANTHROPIC_VERTEX_PROJECT_ID`, `CLOUD_ML_REGION`, `CLAUDE_CODE_USE_VERTEX=1` | `ctg_facts.ctlabs_claude_code.provider.vertexai.{project_id,region}` |

The `vertexai` provider assumes Application Default Credentials (ADC) are already configured on the host (e.g. via `ctlabs_gcloud`).

## OTLP Telemetry

Claude Code can emit OpenTelemetry metrics to a Prometheus OTLP receiver. **Opt-in** — disabled by default.

| Variable | Default | Source |
|---|---|---|
| `ctlabs_claude_code_otlp_enabled` | `false` | `ctg_facts.ctlabs_claude_code.otlp.enabled` |
| `ctlabs_claude_code_otlp_endpoint` | `http://prometheus.ctlabs.internal:9090/v1/metrics` | `ctg_facts.ctlabs_claude_code.otlp.endpoint` |
| `ctlabs_claude_code_otlp_resource_attrs` | `developer`, `team`, `environment` | `ctg_facts.ctlabs_claude_code.otlp.resource_attrs` |

Prometheus promotes `developer`, `team`, `environment` as labels (`prometheus.conf.j2` → `otlp.promote_resource_attributes`).

## Enabling

Set local facts on the target host via `playbooks/ctlabs.yml` → `setup` play. Example for OpenRouter + OTLP on h1/h2/h3:

```json
{
  "provider": {
    "active": "openrouter",
    "openrouter": {
      "api_key": "<key from OPENROUTER_API_KEY env var>",
      "base_url": "https://openrouter.ai/api"
    }
  },
  "otlp": {
    "enabled": true,
    "endpoint": "http://prometheus.ctlabs.internal:9090/v1/metrics",
    "resource_attrs": {
      "developer": "jonesmi",
      "team": "platform",
      "environment": "dev"
    }
  }
}
```

For a host using Vertex AI, override `provider.active` and set `vertexai.*` in inventory vars.

## Tests

```sh
pytest -sv roles/ctlabs_claude_code/tests
```
