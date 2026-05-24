# Ansible Role `ctlabs_ghidra`

## Description
Installs Ghidra (NSA Reverse Engineering Platform) on Debian systems.

## Tags
- `ctlabs_ghidra`
- `ctlabs_ghidra.precheck`
- `ctlabs_ghidra.package`
- `ctlabs_ghidra.config`

## Prechecks
- OS: `debian12`

## Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `ctlabs_ghidra.defaults.pkgs` | see defaults | Packages to install (Temurin JDK 21, unzip) |
| `ctlabs_ghidra.defaults.ghidra.url` | GitHub releases | URL of the Ghidra ZIP |
| `ctlabs_ghidra.defaults.ghidra.link` | `/usr/local/bin/ghidra` | Symlink to ghidraRun |

## Example Playbook
```yaml
- hosts: all
  become: true
  vars:
    ctg_os: debian12
    ctg_os_family: debian
  roles:
    - ctlabs_ghidra
```

## Tests
```sh
ansible-playbook -i localhost, playbook.yml --syntax-check
```
