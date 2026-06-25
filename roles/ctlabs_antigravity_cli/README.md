# Ansible Role `ctlabs_antigravity_cli`

## Ansible Tags

- `ctlabs_antigravity_cli`
- `ctlabs_antigravity_cli.precheck`
- `ctlabs_antigravity_cli.package`
- `ctlabs_antigravity_cli.config`
- `ctlabs_antigravity_cli.service`

## Prechecks

- OS: debian12, kali2025, kali2026, parrot6, parrot7, centos9
- Virtualization: KVM, container

## Description

Installs and configures the [Antigravity CLI](https://antigravity-cli-auto-updater-974169037036.us-central1.run.app) (`agy`) tool.

Downloads the binary from a remote manifest (supports both `tar.gz` archives and raw binaries), verifies via SHA512, and installs it to `/usr/local/bin/agy`. Creates a system user/group (`agy`) and deploys a profile to `/etc/profile.d/agy.sh`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ctlabs_antigravity_cli.defaults.install.manifest_base` | `https://...run.app` | Base URL for platform manifests |
| `ctlabs_antigravity_cli.defaults.install.dir` | `/usr/local/lib/antigravity` | Download/extract directory |
| `ctlabs_antigravity_cli.defaults.install.bin` | `/usr/local/bin/agy` | Installed binary path |
| `ctlabs_antigravity_cli.defaults.config.user` | `agy` | System user |
| `ctlabs_antigravity_cli.defaults.config.group` | `agy` | System group |
| `ctlabs_antigravity_cli.defaults.config.dir` | `/home/agy` | User home directory |

## Tests

```sh
pytest -sv roles/ctlabs_antigravity_cli/tests
```

Validates template/task file existence and `--syntax-check` of the role via a localhost playbook.
