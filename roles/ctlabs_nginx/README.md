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

Site configs live in `{{ conf_dir }}/nginx.d/` (e.g. `/etc/nginx/conf.d/nginx.d/`) and are auto-included by the main `nginx.conf`.

## Tests

```sh
pytest -sv roles/ctlabs_nginx/tests
```
