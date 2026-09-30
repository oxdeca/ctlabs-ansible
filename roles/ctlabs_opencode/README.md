# Ansible Role `ctlabs_opencode`

## Ansible Tags

- `ctlabs_opencode`
- `ctlabs_opencode.precheck`
- `ctlabs_opencode.package`
- `ctlabs_opencode.config`
- `ctlabs_opencode.service`

## Prechecks

- OS: debian12, kali2025, kali2026, parrot6, parrot7, centos9

## Description

Installs [OpenCode](https://opencode.ai) — an AI coding assistant — via npm (`opencode-ai`). Sets up:
- Node.js 22.x via NodeSource (Debian/RedHat)
- `opencode` system user
- Profile snippet at `/etc/profile.d/opencode.sh`
- OpenCode config at `~/.config/opencode/opencode.json` (opencode user only)
- Managed OpenCode config at `/etc/opencode/opencode.json` (applies to **every** OS user, including root)

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ctlabs_opencode.defaults.repos` | NodeSource `node_22.x` | per OS family |
| `ctlabs_opencode.defaults.pkgs.npm` | `[opencode-ai]` | npm packages to install globally |
| `ctlabs_opencode.defaults.config.dir` | `/home/opencode` | opencode user home |
| `ctlabs_opencode.defaults.config.settings.file` | `/home/opencode/.config/opencode/opencode.json` | OpenCode config file (opencode user only) |
| `ctlabs_opencode.defaults.config.commands` | `{end: {...}, graphify: {...}}` | Custom slash commands, rendered into the managed config |
| `ctlabs_opencode.defaults.config.managed.file` | `/etc/opencode/opencode.json` | Managed config file (every user) |
| `ctlabs_opencode.defaults.mcp_servers` | `{graphify: {type: remote, url: "http://127.0.0.1:8080/mcp"}}` | MCP servers to register |

### Custom Commands

OpenCode loads a **managed** config from `/etc/opencode/opencode.json` (Linux) at the highest priority tier, merged in for every OS user regardless of home directory — this is where slash commands like `/end` live so they work for `root` (the interactive user on these lab hosts) as well as the `opencode` service account. Override or add commands via `ctg_facts.ctlabs_opencode.commands` (merged over `ctlabs_opencode.defaults.config.commands`, resolved in `precheck.yml` as `ctlabs_opencode_commands`):

```yaml
ctlabs_opencode:
  defaults:
    config:
      commands:
        end:
          description: "End session — update memory files and save daily notes"
          template: "..."
```

### MCP Servers

The `opencode.json.j2` template includes MCP server configuration from `ctlabs_opencode.mcp_servers`. By default it registers the local `graphify` MCP server. Override or extend the dict to add additional MCP servers:

```yaml
ctlabs_opencode:
  defaults:
    mcp_servers:
      graphify:
        type: remote
        url: http://127.0.0.1:8080/mcp
```

## Tests

```sh
pytest -sv roles/ctlabs_opencode/tests
```
