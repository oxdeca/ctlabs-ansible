# Ansible Role `ctlabs_wazuh`

## Ansible Tags

- `ctlabs_wazuh`
- `ctlabs_wazuh.precheck`
- `ctlabs_wazuh.package`
- `ctlabs_wazuh.config`
- `ctlabs_wazuh.service`

## Prechecks

- OS: debian11, debian12, redhat9, centos9
- Virtualization: KVM, container

## Description

Deploys Wazuh (open-source security monitoring) on Linux hosts. Supports two modes controlled via `ctg_facts.ctlabs_wazuh.role` or `ctlabs_wazuh_role`:

- **server** — deploys Wazuh indexer, manager, and dashboard (all-in-one)
- **agent** — deploys Wazuh agent, connects to a manager

Indexer uses demo security certificates by default (development/testing). Override cert paths via templates for production.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ctg_facts.ctlabs_wazuh.role` | `agent` | Role: `server` or `agent` |
| `ctg_facts.ctlabs_wazuh.server_addr` | `127.0.0.1` | Manager address (agent only) |
| `ctg_facts.ctlabs_wazuh.indexer.network.host` | `127.0.0.1` | Indexer listen address (server) |
| `ctg_facts.ctlabs_wazuh.manager.addr` | `0.0.0.0` | Manager listen address (server) |
| `ctg_facts.ctlabs_wazuh.dashboard.host` | `0.0.0.0` | Dashboard listen address (server) |

## Tests

```sh
pytest -sv roles/ctlabs_wazuh/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.
