# Ansible Role `ctlabs_auditd`

## Ansible Tags

- `auditd`

## Prechecks

- OS: redhat9, centos9, debian11, debian12
- Virtualization: KVM (`ctg_virtype == "kvm"`)

## Rules deployed

Template rendered to `/etc/audit/rules.d/ctlabs-auditd.rules`, covering:

- **identity** — group, passwd, gshadow, shadow, opasswd
- **actions** — sudoers, sudoers.d
- **ssh_config** — sshd_config
- **system-locale** — issue, issue.net, hosts
- **MAC-policy** — /etc/selinux/
- **auditconfig** — /etc/audit/
- **dns_tampering** — /etc/resolv.conf (auid>=1000 only)

Base configuration (`-D`, `-b 8192`, `-f 1`) is inherited from the OS-provided rules file in `/etc/audit/rules.d/`.
