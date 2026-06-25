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
- OpenCode config at `~/.config/opencode/opencode.json`

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ctlabs_opencode.defaults.repos` | NodeSource `node_22.x` | per OS family |
| `ctlabs_opencode.defaults.pkgs.npm` | `[opencode-ai]` | npm packages to install globally |
| `ctlabs_opencode.defaults.config.dir` | `/home/opencode` | opencode user home |
| `ctlabs_opencode.defaults.config.settings.file` | `/home/opencode/.config/opencode/opencode.json` | OpenCode config file |
| `ctlabs_opencode.defaults.mcp_servers` | `{graphify: {type: remote, url: "http://127.0.0.1:8080/mcp"}}` | MCP servers to register |

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
