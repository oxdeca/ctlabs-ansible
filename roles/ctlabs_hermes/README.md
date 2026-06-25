# Ansible Role `ctlabs_hermes`

## Ansible Tags

- `ctlabs_hermes`
- `ctlabs_hermes.precheck`
- `ctlabs_hermes.package`
- `ctlabs_hermes.config`
- `ctlabs_hermes.service`

## Prechecks

- OS: debian12, kali2025, kali2026, parrot6, parrot7, centos9
- Virtualization: KVM, container

## Description

Installs and configures [Hermes Agent](https://github.com/NousResearch/hermes-agent) — an AI agent framework.

Sets up NodeSource repositories (APT pinning for Debian, `yum_repository` for RedHat), installs Node.js + Python dependencies, clones the hermes-agent repo from GitHub, installs via pip (editable), creates a system user/group (`hermes`), and deploys a profile to `/etc/profile.d/hermes.sh`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ctlabs_hermes.defaults.config.repo.url` | `https://github.com/NousResearch/hermes-agent.git` | Git repo URL |
| `ctlabs_hermes.defaults.config.repo.dir` | `/usr/local/lib/hermes-agent` | Clone destination |
| `ctlabs_hermes.defaults.config.user` | `hermes` | System user |
| `ctlabs_hermes.defaults.config.group` | `hermes` | System group |
| `ctlabs_hermes.defaults.config.dir` | `/home/hermes` | User home directory |

## Tests

```sh
pytest -sv roles/ctlabs_hermes/tests
```

Validates template/task file existence and `--syntax-check` of the role via a localhost playbook.
