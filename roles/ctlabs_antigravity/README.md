# Ansible Role `ctlabs_antigravity`

## Ansible Tags

- `ctlabs_antigravity`
- `ctlabs_antigravity.precheck`
- `ctlabs_antigravity.package`
- `ctlabs_antigravity.config`
- `ctlabs_antigravity.service`

## Prechecks

- OS: debian12, kali2025, kali2026, parrot6, parrot7, centos9
- Virtualization: KVM, container

## Description

Installs and configures the [Antigravity CLI](https://antigravity-cli-auto-updater-974169037036.us-central1.run.app) (`antigravity` / `agy`) tool.

Downloads the binary from a remote manifest (supports both `tar.gz` archives and raw binaries), verifies via SHA512, installs it to `/usr/local/bin/antigravity`, and creates a `/usr/local/bin/agy` symlink so both `antigravity` and `agy` commands are supported. Creates a system user/group (`agy`) and deploys a profile to `/etc/profile.d/agy.sh` (setting `COLORTERM=truecolor` and ensuring `/usr/local/bin` and `/usr/local/lib/antigravity` are in `PATH`).

## Configuration

| Variable                                                              | Default                                   | Description                                      |
|-----------------------------------------------------------------------|-------------------------------------------|--------------------------------------------------|
| `ctlabs_antigravity.defaults.install.manifest_base`                   | `https://...run.app`                      | Base URL for platform manifests                  |
| `ctlabs_antigravity.defaults.install.dir`                             | `/usr/local/lib/antigravity`              | Download/extract directory                       |
| `ctlabs_antigravity.defaults.install.bin`                             | `/usr/local/bin/antigravity`              | Installed binary path                            |
| `ctlabs_antigravity.defaults.install.link`                            | `/usr/local/bin/agy`                      | Symlink path for the `agy` command               |
| `ctlabs_antigravity.defaults.config.user`                             | `agy`                                     | System user                                      |
| `ctlabs_antigravity.defaults.config.group`                            | `agy`                                     | System group                                     |
| `ctlabs_antigravity.defaults.config.dir`                              | `/home/agy`                               | User home directory                              |
| `ctlabs_antigravity.defaults.config.settings.file`                    | `~/.gemini/antigravity-cli/settings.json` | Antigravity CLI settings file                    |
| `ctlabs_antigravity.defaults.config.settings.enable_terminal_sandbox` | `false`                                   | `enableTerminalSandbox` value in `settings.json` |

## Tests

```sh
pytest -sv roles/ctlabs_antigravity/tests
```

Validates template/task file existence and `--syntax-check` of the role via a localhost playbook.
