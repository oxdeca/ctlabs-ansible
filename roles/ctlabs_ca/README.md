# Ansible Role `ctlabs_ca`

Creates a lab-local self-signed root CA and per-host server certificates signed by it. The CA and all certs are generated on the **ansible controller** (`delegate_to: localhost`) via `openssl` shell scripts, then copied out to each managed host (Linux and Windows).

## Ansible Tags

- `ctlabs_ca`
- `ctlabs_ca.precheck`
- `ctlabs_ca.config`
- `ctlabs_ca.ca`
- `ctlabs_ca.certs`

## Prechecks

- OS: centos7/8/9, redhat7/8/9, debian11/12, kali2024/2025/2026, ubuntu24, parrot6/7, alpine3, Windows Server (`ctg_os_family == 'windows'`).
- `openssl` must be available on the controller (localhost) — the role does not install it there.

## Config

| Variable                                  | Default                    | Description                                    |
|-------------------------------------------|----------------------------|-------------------------------------------------|
| `ctlabs_ca.defaults.config.dir`           | `/etc/ca-ctlabs`           | Directory (on controller) holding the CA + certs |
| `ctlabs_ca.defaults.config.domain`        | `ctlabs.internal`          | Default domain used to build cert CNs, overridable via `ctg_facts.ctlabs_ca.domain` |
| `ctlabs_ca.defaults.config.ca.name`       | `ca-ctlabs`                | CA file basename / CN                          |
| `ctlabs_ca.defaults.config.ca.bits`       | `4096`                     | CA key size                                    |
| `ctlabs_ca.defaults.config.certs.bits`    | `4096`                     | Server cert key size                           |
| `ctlabs_ca.defaults.config.group`         | `certs`                    | System group owning the copied cert files (Linux only) |
| `ctlabs_ca.defaults.config.perms`         | `0640`                     | Permissions on copied cert files (Linux only)  |
| `ctlabs_ca.defaults.config.windows.dir`   | `C:/ProgramData/ca-ctlabs` | Target directory on Windows hosts              |
| `ctlabs_ca.defaults.config.windows.acl`   | Administrators/System      | ACL entries applied to the Windows CA directory |

**Local fact override** — `/etc/ansible/facts.d/ctlabs_ca.fact` (Linux) or `C:/ProgramData/ansible/facts.d/ctlabs_ca.ps1` (Windows, emits JSON):
```json
{
  "domain": "ctlabs.internal"
}
```

## Behavior

- **CA creation** (`tasks/ca.yml`): the CA is created once per controller. The create block runs when the *target* has no `ca-ctlabs.crt`; `files/create_ctlabs_ca.sh` itself never regenerates a CA as long as both `ca-ctlabs.crt` and `ca-ctlabs.key` exist, so a host that lost its copy cannot rotate the lab CA.
- **Server certs** (`tasks/certs.yml`): one cert per managed host (`{{ ansible_hostname }}.{{ ctlabs_ca_domain }}`), guarded the same way — regenerated only if missing. CN/SAN cover the host FQDN + `CTLABS_HOST` IP.
- **Linux**: the CA cert is installed into the system trust store (`update-ca-certificates` / `update-ca-trust extract`); certs are copied with owner `root`, group `certs`, mode `0640`. The CA directory is `0750 root:certs`.
- **Windows**: nothing is imported into the Windows trust store — the CA cert and the host certs are only dumped into `C:/ProgramData/ca-ctlabs`. The directory inherits no ACEs from `C:/ProgramData` and is restricted to `BUILTIN\Administrators` and `NT AUTHORITY\SYSTEM` (`FullControl`). Import the certs into a store where they are needed (`Import-Certificate`).

### Certificate serials

Both `files/create_ctlabs_ca.sh` (self-signed CA) and `files/create_server_cert.sh` (CA-signed leaf certs) pass `-set_serial` derived from a nanosecond timestamp. This matters when the **same CA name/CN** is generated more than once — e.g. running a lab inside a lab, where the outer and inner lab each run this role and produce their own CA with an identical Issuer DN. Without a randomized serial, two such CAs (or certs) can end up with the same Issuer + Serial, which Firefox rejects with `SEC_ERROR_REUSED_ISSUER_AND_SERIAL`.

## Tests

```sh
pytest -sv roles/ctlabs_ca/tests
```

Validates template/script file existence, that both cert-signing scripts randomize their serial (regression test for `SEC_ERROR_REUSED_ISSUER_AND_SERIAL`), that the CA script keeps an existing CA (only recreates it when the crt or key is missing), the Windows directory/ACL/fact wiring, and `--syntax-check` of the role via a localhost playbook.
