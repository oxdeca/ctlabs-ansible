# Ansible Role `ctlabs_graphify`

## Ansible Tags

- `ctlabs_graphify`
- `ctlabs_graphify.precheck`
- `ctlabs_graphify.package`
- `ctlabs_graphify.config`
- `ctlabs_graphify.service`

## Prechecks

- OS: debian12, centos9, redhat9
- Virtualization: KVM, container

## Description

Installs [Graphify](https://github.com/safishamsi/graphify) (knowledge graph tool for codebases) via pipx. Installs the `graphify` CLI system-wide and sets up a `graphify-mcp` systemd service for the MCP HTTP server.

## Configuration

| Variable                                         | Default                    | Description                   |
|--------------------------------------------------|----------------------------|-------------------------------|
| `ctlabs_graphify.defaults.pipx.bin_dir`          | `/usr/local/bin`           | pipx binary symlink directory |
| `ctlabs_graphify.defaults.pipx.home`             | `/opt/pipx`                | pipx home (venv storage)      |
| `ctlabs_graphify.defaults.config.mcp.host`       | `127.0.0.1`                | MCP HTTP server bind address  |
| `ctlabs_graphify.defaults.config.mcp.port`       | `8080`                     | MCP HTTP server port          |
| `ctlabs_graphify.defaults.config.mcp.graph_file` | `/var/graphify/graph.json` | Graph file path served by MCP |

## Tests

```sh
pytest -sv roles/ctlabs_graphify/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.

## Tools

### `tools/ansible_yaml_extract.py`

Extracts Ansible YAML structure (roles, tasks, playbooks, tags, vars, handlers) into graphify's `graph.json`. Run it against the repo root after `graphify update .` to get YAML content in the graph (graphify skips `.yml`/`.yaml` as "docs" without an API key).

```sh
python3 roles/ctlabs_graphify/tools/ansible_yaml_extract.py
```

No API key needed — uses static parsing, not LLM.
