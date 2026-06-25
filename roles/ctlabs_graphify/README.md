# Ansible Role `ctlabs_graphify`

## Ansible Tags

- `ctlabs_graphify`
- `ctlabs_graphify.precheck`
- `ctlabs_graphify.package`
- `ctlabs_graphify.config`

## Prechecks

- OS: debian12, centos9, redhat9
- Virtualization: KVM, container

## Description

Installs [Graphify](https://github.com/safishamsi/graphify) (knowledge graph tool for codebases) and provides `graphify-update-all` to rebuild graphs for all configured projects.

**Configured projects** (`ctlabs_graphify.defaults.projects`):

| Project | Directory | YAML Extraction |
|---|---|---|
| ctlabs-ansible | `/root/ctlabs-ansible` | Yes (via `ansible_yaml_extract.py`) |
| ctlabs-terraform | `/root/ctlabs-terraform` | No |
| ctlabs-tools | `/root/ctlabs-tools` | No |

On each run, `graphify-update-all`:
1. Runs `graphify update --no-viz --update` on each project (skips heavy HTML viz, only processes changed files)
2. Runs `ansible_yaml_extract.py` for the ansible repo (adds YAML structure without an API key)
3. Each project's `graph.json` stays in its own `graphify-out/` directory

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ctlabs_graphify.defaults.projects` | `[{dir: /root/ctlabs-ansible, yaml_extract: true}, ...]` | Project directories to index |

## Usage

```sh
/usr/local/bin/graphify-update-all
```

## Tests

```sh
pytest -sv roles/ctlabs_graphify/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.

## Tools

### `tools/ansible_yaml_extract.py`

Extracts Ansible YAML structure (roles, tasks, playbooks, tags, vars, handlers) into graphify's `graph.json`. Run against the repo root after `graphify update . --no-viz --update` to get YAML content in the graph (graphify skips `.yml`/`.yaml` as "docs" without an API key).

```sh
python3 roles/ctlabs_graphify/tools/ansible_yaml_extract.py
```

No API key needed — uses static parsing, not LLM. Automatically invoked by `graphify-update-all` for projects with `yaml_extract: true`.
