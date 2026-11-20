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

Site configs are deployed into `{{ conf_dir }}/` (e.g. `/etc/nginx/conf.d/`) and are auto-included by the main `nginx.conf`.

Pass extra server configs via the `nginx` profile fact. Each key is the filename written under `conf_dir`; each value is the file body:

```yaml
nginx:
  h3:
    config:
      servers:
        me.conf: |
          server {
              listen 443 ssl http2;
              server_name example.com;
              ssl_protocols TLSv1.2 TLSv1.3;
              ssl_certificate     /etc/ca-ctlabs/h3.ctlabs.internal.crt;
              ssl_certificate_key /etc/ca-ctlabs/h3.ctlabs.internal.prv;
          }
```

Filenames must match `^[A-Za-z0-9_.-]+\.conf$`.

## Tests

```sh
pytest -sv roles/ctlabs_nginx/tests
```
