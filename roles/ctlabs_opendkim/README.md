# Ansible Role `ctlabs_opendkim`

This role installs and configures OpenDKIM for email signing and verification.

## Ansible Tags

- `ctlabs_opendkim`
- `ctlabs_opendkim.precheck`
- `ctlabs_opendkim.package`
- `ctlabs_opendkim.config`
- `ctlabs_opendkim.service`

## Configuration

| Variable                              | Default                     | Description                        |
|---------------------------------------|-----------------------------|------------------------------------|
| `ctg_facts.ctlabs_opendkim.domain`    | `ansible_domain`            | Domain name for DKIM               |
| `ctg_facts.ctlabs_opendkim.selector`  | MD5 of `ansible_nodename`   | DKIM selector                      |
| `ctg_facts.ctlabs_opendkim.algorithm` | `ed25519`                   | Key algorithm (`ed25519` or `rsa`) |
| `ctg_facts.ctlabs_opendkim.length`    | `256`                       | Key length in bits — fixed at 256 for Ed25519, configurable (e.g. `1024`, `2048`, `3072`, `4096`) for RSA |

## Key Algorithm

- **Ed25519** (default): Generates a 256-bit Ed25519 key. DNS record uses `k=ed25519` with raw 32-byte public key.
- **RSA**: Generates an RSA key via `opendkim-genkey` defaults. DNS record uses `k=rsa` with full SPKI.

The key is generated using `community.crypto.openssl_privatekey` (requires `python3-cryptography` on the target).

## Postfix Integration

This role adds the `postfix` user to the `opendkim` group. You still need to configure Postfix to use the milter:

```text
smtpd_milters         = unix:/run/opendkim/opendkim.sock
non_smtpd_milters     = $smtpd_milters
milter_default_action = accept
```

__/etc/ansible/facts.d/ctlabs_opendkim.fact__

Ed25519 (default):
```json
{
  "domain"    : "ctlabs.internal",
  "algorithm" : "ed25519",
  "length"    : 256
}
```

RSA:
```json
{
  "domain"    : "ctlabs.internal",
  "algorithm" : "rsa",
  "length"    : 2048
}
```
