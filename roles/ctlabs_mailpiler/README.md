# Ansible Role `ctlabs_mailpiler`

## Ansible Tags

- `ctlabs_mailpiler`
- `ctlabs_mailpiler.precheck`
- `ctlabs_mailpiler.package`
- `ctlabs_mailpiler.config`
- `ctlabs_mailpiler.service`

## Prechecks

- OS: debian12
- Virtualization: KVM, container

## Configuration

| Variable                                            | Default                                                       | Description                            |
|-----------------------------------------------------|---------------------------------------------------------------|----------------------------------------|
| `ctlabs_mailpiler.defaults.piler.url`               | *(see defaults)*                                              | piler .deb download URL                |
| `ctlabs_mailpiler.defaults.mysql.root_password`     | `""`                                                          | MariaDB root password                  |
| `ctlabs_mailpiler.defaults.mysql.piler_db`          | `piler`                                                       | Piler database name                    |
| `ctlabs_mailpiler.defaults.mysql.piler_user`        | `piler`                                                       | Piler database user                    |
| `ctlabs_mailpiler.defaults.mysql.piler_password`    | `piler`                                                       | Piler database password                |

## Tests

```sh
pytest -sv roles/ctlabs_mailpiler/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.
