# Ansible Role `ctlabs_opendkim`\

This role installs and configures OpenDKIM for email signing and verification.

## Ansible Tags

- `ctlabs_opendkim`
- `ctlabs_opendkim.precheck`
- `ctlabs_opendkim.package`
- `ctlabs_opendkim.config`
- `ctlabs_opendkim.service`\

## Prechecks

- Supported OS: RedHat 9, CentOS 9, Debian 11, Debian 12

## Configuration

| Variable                              | Default          | Description          |
|---------------------------------------|------------------|----------------------|
| `ctg_facts.ctlabs_opendkim.domain`    | `ansible_domain` | Domain name for DKIM |
| `ctg_facts.ctlabs_opendkim.selector`  | `default`        | DKIM selector        |
| `ctg_facts.ctlabs_opendkim.algorithm` | `ed25519`        | Key algorithm        |
| `ctg_facts.ctlabs_opendkim.bits`      | `2048`           | Key length (for RSA) |

## Postfix Integration

This role adds the `postfix` user to the `opendkim` group. You still need to configure Postfix to use the milter:

```text
smtpd_milters         = unix:/run/opendkim/opendkim.sock
non_smtpd_milters     = $smtpd_milters
milter_default_action = accept
```

__/etc/ansible/facts.d/ctlabs_opendkim.fact__

```json
  {
    "domain"   : "example.com",
    "selector" : "20260519",
    "algorithm": "rsa",
    "bits"     " 4096"
  }
```

