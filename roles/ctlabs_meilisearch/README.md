# Ansible Role `ctlabs_meilisearch`

## Ansible Tags

- `ctlabs_meilisearch`
- `ctlabs_meilisearch.precheck`
- `ctlabs_meilisearch.package`
- `ctlabs_meilisearch.config`
- `ctlabs_meilisearch.service`

## Prechecks

- OS: debian12, centos9
- Virtualization: KVM, container

## Description

Installs Meilisearch (Rust-based search engine) from the official GitHub release binary. Configured via environment file with master key, listen address, and snapshot schedule.

## Configuration

| Variable                                    | Default                      | Description                    |
|---------------------------------------------|------------------------------|--------------------------------|
| `ctlabs_meilisearch.defaults.config.key`    | `secret123!`                 | Meilisearch master API key     |
| `ctlabs_meilisearch.defaults.config.addr`   | `127.0.0.1:7700`             | Listen address                 |
| `ctlabs_meilisearch.defaults.config.db_path`| `/var/lib/meilisearch`       | Data directory                 |
| `ctlabs_meilisearch.defaults.config.snapshot_interval` | `86400`           | Snapshot interval in seconds   |

## Tests

```sh
pytest -sv roles/ctlabs_meilisearch/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.
