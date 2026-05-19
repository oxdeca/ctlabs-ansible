# Ansible Role `ctlabs_postfix`

## Ansible Tags

- `ctlabs_postfix`
- `ctlabs_postfix.precheck`
- `ctlabs_postfix.package`
- `ctlabs_postfix.config`
- `ctlabs_postfix.service`
- `ctlabs_postfix.helper`

## Prechecks

- OS: redhat7, redhat8, redhat9, centos7, centos8, centos9

## DKIM

DKIM signing is handled by the separate `ctlabs_dkim` role (declared as a dependency in `meta/main.yml`). See `roles/ctlabs_dkim/README.md`.

## Tests

```sh
pytest -sv roles/ctlabs_postfix/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.
