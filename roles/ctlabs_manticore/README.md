# Ansible Role `ctlabs_manticore`

## Ansible Tags

- `ctlabs_manticore`
- `ctlabs_manticore.precheck`
- `ctlabs_manticore.package`
- `ctlabs_manticore.service`

## Prechecks

- OS: debian12, centos9
- Virtualization: KVM, container

## Description

Installs Manticore Search (a drop-in Sphinx replacement). Provides the `searchd` binary used by piler's `pilersearch` service.

The default `manticore` systemd service is kept stopped — piler uses its own `pilersearch.service` wrapping `searchd` with `/etc/piler/manticore.conf`.

## Tests

```sh
pytest -sv roles/ctlabs_manticore/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.
