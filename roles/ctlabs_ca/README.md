# Ansible Role `ctlabs_ca`

Creates a lab-local self-signed root CA and per-host server certificates signed by it. The CA and all certs are generated on the **ansible controller** (`delegate_to: localhost`) via `openssl` shell scripts, then copied out to each managed host.

## Ansible Tags

- `ctlabs_ca`
- `ctlabs_ca.precheck`
- `ctlabs_ca.config`
- `ctlabs_ca.ca`
- `ctlabs_ca.certs`

## Prechecks

- OS: centos7/8/9, redhat7/8/9, debian11/12, kali2024/2025/2026, ubuntu24, parrot6/7, alpine3
- `openssl` must be available on the controller (localhost) — the role does not install it there.

## Config

| Variable                                | Default          | Description                                    |
|------------------------------------------|------------------|-------------------------------------------------|
| `ctlabs_ca.defaults.config.dir`           | `/etc/ca-ctlabs` | Directory (on controller) holding the CA + certs |
| `ctlabs_ca.defaults.config.domain`        | `ctlabs.internal`| Default domain used to build cert CNs, overridable via `ctg_facts.ctlabs_ca.domain` |
| `ctlabs_ca.defaults.config.ca.name`       | `ca-ctlabs`      | CA file basename / CN                          |
| `ctlabs_ca.defaults.config.ca.bits`       | `4096`           | CA key size                                    |
| `ctlabs_ca.defaults.config.certs.bits`    | `4096`           | Server cert key size                           |
| `ctlabs_ca.defaults.config.group`         | `certs`          | System group owning the copied cert files      |
| `ctlabs_ca.defaults.config.perms`         | `0640`           | Permissions on copied cert files               |

**Local fact override** (`/etc/ansible/facts.d/ctlabs_ca.fact`):
```json
{
  "domain": "ctlabs.internal"
}
```

## Behavior

- **CA creation** (`tasks/ca.yml`): runs once per controller — guarded by `stat` on `{{ config.dir }}/{{ ca.name }}.crt`. If the CA already exists it is reused, never regenerated. The CA cert is also installed into the managed host's system trust store (`update-ca-certificates` / `update-ca-trust extract`).
- **Server certs** (`tasks/certs.yml`): one cert per managed host (`{{ ansible_hostname }}.{{ ctlabs_ca_domain }}`), guarded the same way — regenerated only if missing. CN/SAN cover the host FQDN + `CTLABS_HOST` IP. Signed by the CA, then copied to the host as `.crt` (chain), `.crt`/`.key`/`.prv` (host cert, encrypted and unencrypted private key).

### Certificate serials

Both `files/create_ctlabs_ca.sh` (self-signed CA) and `files/create_server_cert.sh` (CA-signed leaf certs) pass `-set_serial` derived from a nanosecond timestamp. This matters when the **same CA name/CN** is generated more than once — e.g. running a lab inside a lab, where the outer and inner lab each run this role and produce their own CA with an identical Issuer DN. Without a randomized serial, two such CAs (or certs) can end up with the same Issuer + Serial, which Firefox rejects with `SEC_ERROR_REUSED_ISSUER_AND_SERIAL`.

This only affects **newly created** CAs/certs (the `stat`-guarded create blocks run once) — an existing lab's CA keeps whatever serial it was created with; rebuild the lab to pick up a fresh, randomized serial.

## Tests

```sh
pytest -sv roles/ctlabs_ca/tests
```

Validates template/script file existence, that both cert-signing scripts randomize their serial (regression test for `SEC_ERROR_REUSED_ISSUER_AND_SERIAL`), and `--syntax-check` of the role via a localhost playbook.
