# Ansible Role `ctlabs_tika`

## Ansible Tags

- `ctlabs_tika`
- `ctlabs_tika.precheck`
- `ctlabs_tika.package`
- `ctlabs_tika.config`
- `ctlabs_tika.service`

## Prechecks

- OS: debian12, centos9
- Virtualization: KVM, container

## Description

Installs Apache Tika content extraction server. Sets up OpenJDK 17 JRE, downloads the tika-server-standard JAR from Apache, and runs it as a systemd service.

## Configuration

| Variable                              | Default                      | Description                    |
|---------------------------------------|------------------------------|--------------------------------|
| `ctlabs_tika.defaults.config.addr`    | `127.0.0.1`                  | Listen address                 |
| `ctlabs_tika.defaults.config.port`    | `9998`                       | Listen port                    |
| `ctlabs_tika.defaults.download.jar`   | `/opt/tika/tika-server.jar`  | JAR install path               |

## Tests

```sh
pytest -sv roles/ctlabs_tika/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.
