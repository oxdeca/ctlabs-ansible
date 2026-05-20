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

## Tests

```sh
pytest -sv roles/ctlabs_postfix/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.
