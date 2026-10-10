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
- `ctlabs_ad.facts` (setup phase)

## Configuration

#### `ctg_facts.ctlabs_ad.*` (local fact, from the ctlabs `ad` setup profile)

Resolved per host as role var -> local fact -> default.

| Fact                         | Description                         |
|------------------------------|-------------------------------------|
| `role`                       | `master` / `slave` / `member`       |
| `domain`                     | AD DNS domain name                  |
| `realm`                      | Kerberos realm (default upper of domain) |
| `netbios`                    | NetBIOS name                        |
| `master`                     | FQDN of the master DC (slave/member)|
| `leave`                      | `true` -> a `member` leaves instead of joining |

Minimal setup profile:

```yaml
# ctlabs/labs/setup_profiles.yml
ad:
  dc1: { role: master, domain: ad.ctlabs.internal }
  dc2: { role: slave,  domain: ad.ctlabs.internal, master: dc1.ad.ctlabs.internal }
```

### Role Variables

Role-scoped overrides (used when no local fact is present, e.g. ad-hoc runs):

| VAR                          | Description                                                        |
|------------------------------|--------------------------------------------------------------------|
| `ctlabs_ad_role`             | `master` / `slave` / `member`                                      |
| `ctlabs_ad_domain`           | AD DNS domain, default `ad.ctlabs.internal`                        |
| `ctlabs_ad_leave`            | `true` -> a `member` leaves the domain instead of joining          |
| `ctlabs_ad_safe_mode_password`   | DSRM / safe-mode password (DC only); else read from Vault      |
| `ctlabs_ad_admin_user`           | domain-admin user; else Vault (member/slave)                   |
| `ctlabs_ad_admin_password`       | domain-admin password; else Vault (member/slave)              |

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
