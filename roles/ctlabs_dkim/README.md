# Ansible Role `ctlabs_dkim`

## Ansible Tags

| Tag | Description |
|-----|-------------|
| `ctlabs_dkim` | All tasks |
| `ctlabs_dkim.precheck` | OS support check, variable resolution |
| `ctlabs_dkim.package` | Install packages (gcc, sendmail-milter-devel, python3-devel, etc.) + pip dkimpy-milter |
| `ctlabs_dkim.config` | Create user, config, keys, runtime directory |
| `ctlabs_dkim.service` | systemd drop-in, service start |

## Prechecks

- Supported OS: `redhat8`, `redhat9`, `centos8`, `centos9`

## Configuration

Override via `ctg_facts.ctlabs_dkim.*` or playbook vars:

| Variable | Default | Description |
|----------|---------|-------------|
| `ctlabs_dkim_selector` | `default` | DKIM selector |
| `ctlabs_dkim_socket` | `inet:localhost:8891` | Milter listen socket |
| `ctlabs_dkim.defaults.keys.dir` | `/etc/dkimpy-milter/keys` | Key storage directory |
| `ctlabs_dkim.defaults.keys.bits` | `2048` | RSA key size |
