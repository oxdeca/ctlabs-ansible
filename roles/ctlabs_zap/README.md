# Ansible Role `ctlabs_zap`

## Description
Installs OWASP ZAP (Zed Attack Proxy) on Debian systems.

## Tags
- `ctlabs_zap`
- `ctlabs_zap.precheck`
- `ctlabs_zap.package`
- `ctlabs_zap.service`

## Prechecks
- OS: `debian12`
- Virtualization: `kvm`

## Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `ctlabs_zap.defaults.pkgs` | see defaults | Packages to install (Java, Firefox) |
| `ctlabs_zap.defaults.zap.url` | `https://download.opensuse.org/.../zap_{{ versions.zap }}-1_amd64.deb` | URL of the ZAP .deb package |
| `ctlabs_zap.defaults.zap.tmpdir` | `/tmp` | Temporary directory for download |
| `ctlabs_zap.defaults.zap.deb_file` | `zap_{{ versions.zap }}-1_amd64.deb` | Filename of the downloaded .deb |
| `ctlabs_zap.defaults.zap.bin_path` | `/opt/ZAP_{{ versions.zap }}/zap.sh` | Path to the ZAP startup script after install |
| `ctlabs_zap.defaults.zap.link` | `/usr/local/bin/zap` | Symlink created for easy execution |
| `ctlabs_zap.defaults.config.port` | `8080` | Port ZAP will listen on |
| `ctlabs_zap.defaults.config.api_key` | `secret123!` | API key for ZAP daemon |
| `ctlabs_zap.defaults.service.name` | `zap.service` | Systemd unit name |
| `ctlabs_zap.defaults.service.user` | `zap` | User to run ZAP (system user) |
| `ctlabs_zap.defaults.service.group` | `zap` | Group for ZAP |
| `ctlabs_zap.defaults.service.description` | `OWASP ZAP` | Description for systemd unit |

## Example Playbook
```yaml
- hosts: all
  become: true
  vars:
    ctg_os: debian12
    ctg_os_family: debian
    ctg_virtype: kvm
    ctg_systemd_dir: /etc/systemd/system
  roles:
    - ctlabs_zap
```

## Tests
Run syntax check:
```sh
ansible-playbook -i localhost, playbook.yml --syntax-check
```

Add any role‑specific tests in `tests/` as needed.
