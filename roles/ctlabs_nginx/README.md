# Ansible Role `ctlabs_nginx`

## Ansible Tags

- `ctlabs_nginx`
- `ctlabs_nginx.precheck`
- `ctlabs_nginx.package`
- `ctlabs_nginx.config`
- `ctlabs_nginx.service`

## Prechecks

- OS: redhat9, centos9, debian11, debian12

## Configuration

Site configs are deployed directly into `{{ conf_dir }}/` (e.g. `/etc/nginx/conf.d/`) and are auto-included by the main `nginx.conf`.

## Tests

```sh
pytest -sv roles/ctlabs_nginx/tests
```
