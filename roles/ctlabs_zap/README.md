# Ansible Role `ctlabs_zap`

## Description
Installs OWASP ZAP (Zed Attack Proxy) on Debian systems.

## Tags
- `ctlabs_zap`
- `ctlabs_zap.precheck`
- `ctlabs_zap.package`
- `ctlabs_zap.config`

## Prechecks
- OS: `debian12`

## Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `ctlabs_zap.defaults.pkgs` | see defaults | Packages to install (Temurin JDK 21, Firefox) |
| `ctlabs_zap.defaults.zap.url` | `https://download.opensuse.org/.../zap_{{ versions.zap }}-1_amd64.deb` | URL of the ZAP .deb package |
| `ctlabs_zap.defaults.zap.tmpdir` | `/tmp` | Temporary directory for download |
| `ctlabs_zap.defaults.zap.deb_file` | `zap_{{ versions.zap }}-1_amd64.deb` | Filename of the downloaded .deb |
| `ctlabs_zap.defaults.zap.bin_path` | `/usr/share/zap/zap.sh` | Path to the ZAP startup script after install |
| `ctlabs_zap.defaults.zap.link` | `/usr/local/bin/zap` | Symlink created for easy execution |
| `ctlabs_zap.defaults.desktop.name` | `OWASP ZAP` | Application name in menu |
| `ctlabs_zap.defaults.desktop.icon` | `/usr/share/zap/zap.ico` | Icon path for desktop entry |

## Example Playbook
```yaml
- hosts: all
  become: true
  vars:
    ctg_os: debian12
    ctg_os_family: debian
  roles:
    - ctlabs_zap
```

## Tests
Run syntax check:
```sh
ansible-playbook -i localhost, playbook.yml --syntax-check
```

Add any role‑specific tests in `tests/` as needed.
