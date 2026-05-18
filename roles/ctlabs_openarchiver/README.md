# Ansible Role `ctlabs_openarchiver`

## Ansible Tags

- `ctlabs_openarchiver`
- `ctlabs_openarchiver.precheck`
- `ctlabs_openarchiver.package`
- `ctlabs_openarchiver.config`
- `ctlabs_openarchiver.service`

## Prechecks

- OS: debian12, centos9
- Virtualization: KVM, container

## Description

Installs the OpenArchiver email archiving platform natively. Components:

* **Node.js 22** from NodeSource repository
* **pnpm** via corepack
* **OpenArchiver source** cloned from GitHub, built with `pnpm build:oss`
* **Systemd services**: `openarchiver-web.service` (backend + frontend on ports 4000/3000) and `openarchiver-worker.service` (ingestion/indexing/sync workers)
* **Database schema** created via `pnpm db:migrate`

Depends on external roles: `ctlabs_postgresql`, `ctlabs_redis` (or `ctlabs_valkey`), `ctlabs_meilisearch`, `ctlabs_tika`.

## Configuration

| Variable                                            | Default                      | Description                          |
|-----------------------------------------------------|------------------------------|--------------------------------------|
| `ctlabs_openarchiver.defaults.config.app.url`        | `http://localhost:3000`       | Public-facing application URL        |
| `ctlabs_openarchiver.defaults.config.db.*`           | *(see defaults)*              | PostgreSQL connection credentials    |
| `ctlabs_openarchiver.defaults.config.redis.*`        | *(see defaults)*              | Redis/Valkey connection credentials  |
| `ctlabs_openarchiver.defaults.config.meilisearch.*`  | *(see defaults)*              | Meilisearch connection credentials   |
| `ctlabs_openarchiver.defaults.config.tika.url`       | `http://localhost:9998`       | Apache Tika endpoint                 |

## Tests

```sh
pytest -sv roles/ctlabs_openarchiver/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.
