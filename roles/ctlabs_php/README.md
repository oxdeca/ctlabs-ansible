# Ansible Role `ctlabs_php`

## Ansible Tags

- `ctlabs_php`
- `ctlabs_php.precheck`
- `ctlabs_php.package`
- `ctlabs_php.config`
- `ctlabs_php.service`

## Prechecks

- OS: redhat9, centos9, debian11, debian12

## Configuration

PHP-FPM pool listens on a Unix socket at `{{ socket_dir }}/php-fpm.sock`. Intended to be used alongside `ctlabs_httpd` (Apache mod_proxy_fcgi) or `ctlabs_nginx` (proxy_pass).

The FPM pool user/group defaults to the web server user for the OS family (`www-data` on Debian, `apache` on Redhat). Override per-host via local facts or playbook vars:

| Fact / Var                        | Default                                                | Description            |
|-----------------------------------|--------------------------------------------------------|------------------------|
| `ctg_facts.ctlabs_php.fpm_user`   | `www-data` (Debian) / `apache` (Redhat)                | PHP-FPM pool user      |
| `ctg_facts.ctlabs_php.fpm_group`  | `www-data` (Debian) / `apache` (Redhat)                | PHP-FPM pool group     |

Set to `nginx` when using `ctlabs_nginx` on Redhat.

## Tests

```sh
pytest -sv roles/ctlabs_php/tests
```
