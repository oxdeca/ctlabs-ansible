# Ansible Role `ctlabs_ad`

Manage Windows Active Directory. The role is role-aware: a host is either a
**domain controller** (`master` / `slave`) or a **member** (`member`, the
default), which is joined to / removed from an existing domain.

The effective role and domain are resolved **per host** with the following
precedence:

1. a role-scoped var (`ctlabs_ad_role`, `ctlabs_ad_domain`, ...)
2. the `ctlabs_ad` **local fact** (written by `tasks/facts.yml` from the ctlabs
   `ad` setup profile, e.g. `dc1: { role: master, domain: ad.ctlabs.internal }`)
3. the role defaults (`ad.ctlabs.internal`, `member`, ...)

Configuration is deliberately per host via local facts (never global
`CTLABS_AD_*` environment variables) so that, e.g., `dc1` can be a `master`,
`dc2` a `slave` and every other Windows host a plain `member` in the same run.

## Ansible Tags

- `ctlabs_ad`
- `ctlabs_ad.precheck`
- `ctlabs_ad.package`
- `ctlabs_ad.config`
- `ctlabs_ad.dc`
- `ctlabs_ad.join`
- `ctlabs_ad.service`
- `ctlabs_ad.leave`
- `ctlabs_ad.ldaps`
- `ctlabs_ad.keytab`
- `ctlabs_ad.facts` (setup phase)

## Configuration

#### `ctg_facts.ctlabs_ad.*` (local fact, from the ctlabs `ad` setup profile)

Resolved per host as role var -> local fact -> default.

| Fact                         | Description                                    |
|------------------------------|------------------------------------------------|
| `role`                       | `master` / `slave` / `member`                  |
| `domain`                     | AD DNS domain name                             |
| `realm`                      | Kerberos realm (default upper of domain)       |
| `netbios`                    | NetBIOS name                                   |
| `master`                     | FQDN of the master DC (slave/member)           |
| `leave`                      | `true` -> a `member` leaves instead of joining |
| `dns_servers`                | DC-only: eth1 (production) DNS resolvers, default ns1/ns2/8.8.8.8 |
| `ldaps`                      | DC-only: `true` -> serve LDAPS with the `ctlabs_ca` host cert (default `false`) |

Minimal setup profile:

```yaml
# ctlabs/labs/setup_profiles.yml
ad:
  dc1: { role: master, domain: ad.ctlabs.internal }
  dc2: { role: slave,  domain: ad.ctlabs.internal, master: dc1.ad.ctlabs.internal }
```

### Role Variables

Role-scoped overrides (used when no local fact is present, e.g. ad-hoc runs):

| VAR                            | Description                                                        |
|--------------------------------|--------------------------------------------------------------------|
| `ctlabs_ad_role`               | `master` / `slave` / `member`                                      |
| `ctlabs_ad_domain`             | AD DNS domain, default `ad.ctlabs.internal`                        |
| `ctlabs_ad_leave`              | `true` -> a `member` leaves the domain instead of joining          |
| `ctlabs_ad_safe_mode_password` | DSRM / safe-mode password (DC only); else read from Vault          |
| `ctlabs_ad_admin_user`         | domain-admin user; else Vault (member/slave)                       |
| `ctlabs_ad_admin_password`     | domain-admin password; else Vault (member/slave)                   |
| `ctlabs_ad_dns_servers`        | DC-only: eth1 DNS resolvers, default ns1/ns2/8.8.8.8               |
| `ctlabs_ad_ldaps`              | DC-only: `true` -> LDAPS with the `ctlabs_ca` host cert            |

### Credentials

The DC safe-mode password (`ctlabs_ad_safe_mode_password`) and the domain-admin
credentials (`ctlabs_ad_admin_user` / `ctlabs_ad_admin_password`) come from the
role vars above, else from Vault (`ctlabs_ad.defaults.vault.secrets.*`).

- `member` / `slave` authenticate with the domain-admin credentials (Vault).
- `master` creates a new forest; the DC-side OU work runs as the image's
  built-in `Administrator` (`config.dc.admin_user` /
  `config.dc.admin_password`) unless overridden. Note the DSRM / safe-mode
  password only guards directory-services restore mode — it is **not** the
  domain Administrator password.

Secrets are intentionally **not** written to the local fact file.

## Behaviour

| Role     | Action                                                                 |
|----------|------------------------------------------------------------------------|
| `master` | `microsoft.ad.domain` — create the forest + first DC, then the OU tree |
| `slave`  | `microsoft.ad.domain_controller` — promote a replica DC                |
| `member` | `microsoft.ad.membership` — join (`domain`) / leave (`workgroup`)      |

The OU tree is `ou=<env>,ou=servers,ou=ctlabs,<domain dn>` (env from the
`ctlabs` local fact, default `dev`).

## LDAPS (`tasks/ldaps.yml`, tag `ctlabs_ad.ldaps`)

Opt-in per DC (`ldaps: true` in the `ad` setup profile or `-e ctlabs_ad_ldaps=true`).
Uses the host certificate issued by `ctlabs_ca`
(`C:/ProgramData/ca-ctlabs/<host>.<ca domain>.{crt,key,prv}`; `.key` is
password protected, `.prv` is not). AD DS binds LDAPS on its own to a cert in
`LocalMachine\My` that has a private key, the *Server Authentication* EKU and
the DC's FQDN as subject/SAN, so the role:

1. validates on the controller that the cert carries `DNS:<host>.<ad domain>`
   and the serverAuth EKU (fails with a hint otherwise),
2. builds a PFX on the controller from `.crt` + `.prv` + CA cert (random
   password, never stored; PowerShell 5.1 on the DC cannot do this),
3. imports it into `LocalMachine\My` unless that thumbprint is already there,
   imports the lab CA into `LocalMachine\Root`, deletes the PFX again,
4. triggers `renewServerCertificate` and verifies that port 636 presents
   exactly that certificate.

**The cert needs the AD FQDN as extra SAN.** `ctlabs_ca` names the cert
`<host>.ctlabs.internal`, the DC is `<host>.ad.ctlabs.internal`. Add it via the
`ctlabs_ca` fact (`san: [dc1.ad.ctlabs.internal]`) and re-issue the cert
(`ctlabs_ca` never regenerates an existing one: remove
`/etc/ca-ctlabs/<host>.ctlabs.internal.*` on the controller and the copies in
`C:/ProgramData/ca-ctlabs` on the DC first).

## Dedicated service-account keytabs (`tasks/keytab.yml`, tag `ctlabs_ad.keytab`)

Opt-in per DC (`keytabs: [...]` in the `ad` setup profile or `-e ctlabs_ad_keytabs=...`),
for consumers that need GSSAPI/Kerberos auth against AD without a plaintext
password anywhere in their own config - e.g. `ctlabs_slapd`'s `idassert-bind`.

```yaml
# ctlabs/labs/setup_profiles.yml
ad:
  dc1:
    role: master
    domain: ad.ctlabs.internal
    keytabs:
      - name: svc-slapd   # principal defaults to `name` if omitted
```

For each entry the role:

1. creates (or updates) an AD user `name` with `password_never_expires` +
   `user_cannot_change_password`, in `ou_path` (default: this DC's own
   `ou=<env>,ou=servers,ou=ctlabs,<domain dn>`), with `principal` (default:
   `name`) as its UPN - a plain Kerberos client identity, not a service SPN,
2. runs `ktpass` on the DC with a random, never-stored password to reset the
   account's password and extract a matching keytab (`-crypto AES256-SHA1
   -ptype KRB5_NT_PRINCIPAL`),
3. fetches the keytab to the controller at `/etc/keytabs/<name>.keytab`
   (`0640`) - same controller-staging broker pattern `ctlabs_ca` uses for
   certificates - and deletes it from the DC.

**Idempotent by staged file, not by AD state**: step 2 resets the account's
password on every run, so once `<name>.keytab` exists on the controller it is
never regenerated. To rotate a keytab, delete the staged file (this also
causes the account's password to be reset the next run).

Only the AD-side half lives here - a consumer (e.g. `ctlabs_slapd`) copies the
staged keytab onto its own host and points its GSSAPI client config at it; see
that role's README.

## Network Requirements

| PROTO | DST-IP | DST-PORT | DESC         |
|-------|--------|----------|--------------|
| TCP   | host   | `22`     | ssh          |
| TCP   | host   | `3389`   | winrdp       |
| TCP   | host   | `5986`   | ntlm - https |
| TCP/UDP | host | `53`     | dns          |
| TCP/UDP | host | `88`     | kerberos     |
| TCP   | host   | `389`    | ldap         |
| TCP   | host   | `636`    | ldaps        |
| TCP   | host   | `445`    | smb          |

## Examples

```bash
# create the first (master) domain controller (fact overrides the var)
sh# ansible-playbook -i ./inventories/hosts.ini ./playbooks/ctlabs.yml -t ctlabs_ad.dc -e ctlabs_ad_role=master -l dc1

# join a regular host to the domain (role/domain come from its local fact)
sh# ansible-playbook -i ./inventories/hosts.ini ./playbooks/ctlabs.yml -t ctlabs_ad -l win-vm01

# remove a host from the domain
sh# ansible-playbook -i ./inventories/hosts.ini ./playbooks/ctlabs.yml -t ctlabs_ad -e ctlabs_ad_leave=true -l win-vm01
```
