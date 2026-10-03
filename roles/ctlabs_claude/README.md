# Ansible Role `ctlabs_claude`

## Ansible Tags

- `ctlabs_claude`
- `ctlabs_claude.precheck`
- `ctlabs_claude.package`
- `ctlabs_claude.config`
- `ctlabs_claude.service`

## Prechecks

- OS: debian12, kali2025, kali2026, parrot6, parrot7, centos9

## Description

Installs [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) via npm (`@anthropic-ai/claude-code`). Sets up:

- Node.js 22.x via NodeSource (Debian/RedHat)
- `claude` system user
- Claude Code config at `~/.claude/settings.json`
- Custom slash commands at `~/.claude/commands/*.md`

Both provider configuration and OTLP telemetry are **opt-in** — disabled by default. Enable via local facts.

Note: `~` is expanded on the target host by the `ansible_user` connecting (root on every lab host today, since these roles run with no `become_user`) — not the `claude` system user's `/home/claude`. This matches existing `settings.json` behavior, so slash commands land wherever `claude`/`opencode` are actually run interactively.

## Provider Configuration

Claude Code supports multiple API providers. Select exactly one via `provider.active` in local facts.

| Provider | Env vars set | Local fact path |
|---|---|---|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | `ctg_facts.ctlabs_claude.provider.anthropic.api_key` |
| `openrouter` | `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_SKIP_FAST_MODE_ORG_CHECK=1` | `ctg_facts.ctlabs_claude.provider.openrouter.{api_key,base_url}` |
| `vertexai` | `ANTHROPIC_API_KEY=""`, `CLAUDE_CODE_USE_VERTEX=1`, `ANTHROPIC_VERTEX_PROJECT_ID`, `CLOUD_ML_REGION`, `GCE_METADATA_HOST` | `ctg_facts.ctlabs_claude.provider.vertexai.{project_id,region}` |

The `vertexai` provider assumes Application Default Credentials (ADC) are already configured on the host (e.g. via `ctlabs_gcloud`).

## OTLP Telemetry

Claude Code can emit OpenTelemetry metrics to a Prometheus OTLP receiver. **Opt-in** — disabled by default.

Configured via `ctg_facts.ctlabs_claude.otlp` (merged over `ctlabs_claude.defaults.config.otlp`):

| Key | Default | Description |
|---|---|---|
| `enabled` | `false` | Enable OTLP metric export |
| `endpoint` | `http://prometheus.ctlabs.internal:9090/v1/metrics` | OTLP receiver URL |
| `resource_attrs` | `user.email=<ansible_user>` | `OTEL_RESOURCE_ATTRIBUTES` value |

## Preferences

Claude Code UI/model preferences are configured via `ctg_facts.ctlabs_claude.preferences` (merged over `ctlabs_claude.defaults.config.preferences`):

| Key | Default | Description |
|---|---|---|
| `model` | `claude-sonnet-4-6` | Default model |
| `theme` | `dark` | UI theme |
| `always_thinking` | `false` | Enable extended thinking |
| `fast_mode` | `true` | Enable fast mode |
| `fallback_model` | `["haiku"]` | Fallback model list |
| `gce_metadata_host` | `""` | `GCE_METADATA_HOST` override (vertexai only) |

## Custom Commands

Slash commands are rendered as individual Markdown files in `~/.claude/commands/` via `ctg_facts.ctlabs_claude.commands` (merged over `ctlabs_claude.defaults.config.commands`, resolved in `precheck.yml` as `ctlabs_claude_commands`). Each key becomes `<name>.md`:

```yaml
ctlabs_claude:
  defaults:
    config:
      commands:
        end:
          description: "End session — update memory files and save daily notes"
          template: "..."
```

## Local Facts Example

`/etc/ansible/facts.d/ctlabs_claude.fact`:

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
  },
  "dnsmasq": {
    "records": [
      { "name": "prometheus.mon.ctlabs.internal", "ip": "10.9.32.14" }
    ]
  }
}
```

## dnsmasq Host Records

Some OTLP/provider endpoints (e.g. a corporate Prometheus OTLP receiver) resolve to a
private/VPN-only IP that ctlabs' own DNS infrastructure has no reason to know about.
`ctg_facts.ctlabs_claude.dnsmasq.records` renders one `host-record=<name>,<ip>` line per
entry into `/etc/dnsmasq.d/claude.conf` (static, not derived from `otlp.endpoint` —
set it to whatever hostname actually needs pinning) and restarts `dnsmasq` on change.
Empty list (the default) is a complete no-op — nothing is written, nothing restarted.

| Key | Default | Description |
|---|---|---|
| `dnsmasq.records` | `[]` | List of `{name, ip}` static host-record entries |

## Tests

```sh
pytest -sv roles/ctlabs_claude/tests
```
