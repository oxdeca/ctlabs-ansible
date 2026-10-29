# Ansible Role `ctlabs_slapd`

Configure OpenLDAP (`slapd`) as a proxy (`back_ldap`/`back_meta`) in front of
an Active Directory DC, rewriting POSIX attributes to their AD equivalents
(`uid` -> `sAMAccountName`, etc.).

## Ansible Tags

- `ctlabs_slapd`
- `ctlabs_slapd.precheck`
- `ctlabs_slapd.package`
- `ctlabs_slapd.config`
- `ctlabs_slapd.service`
- `ctlabs_slapd.facts` (setup phase)

## Prechecks

Supported OS: `debian11`, `debian12`, `centos9`.

## Config

Proxy databases are a list, resolved as role var (`ctlabs_slapd_dbs`) -> local
fact (`ctg_facts.ctlabs_slapd.dbs`) -> role default
(`ctlabs_slapd.defaults.config.dbs`).

Each entry's `bind` map controls how this host authenticates to the AD DC
for `idassert-bind`:

| `bind.method` | Credentials in `slapd.conf`            | Notes                                   |
|---------------|-----------------------------------------|----------------------------------------|
| `simple`      | `binddn`/`credentials` (plaintext pass) | Default; simplest, weakest.            |
| `sasl`        | none - only a keytab file path          | GSSAPI/Kerberos; see below.            |

### `bind.method: sasl` (GSSAPI)

```yaml
dbs:
  - type  : ldap
    suffix: dc=ad,dc=ctlabs,dc=internal
    uri   : ldaps://dc2.ctlabs.internal ldaps://dc1.ctlabs.internal
    bind:
      method  : sasl
      saslmech: gssapi
      authcid : svc-slapd
      realm   : AD.CTLABS.INTERNAL
      keytab  : svc-slapd   # basename; see keytab.src_dir/dest_dir below
```

The keytab is produced by `ctlabs_ad`'s dedicated service-keytab feature
(`ctlabs_ad.defaults.config.dc.keytabs`) and staged on the **controller** at
`ctlabs_slapd.defaults.config.keytab.src_dir` (default `/etc/keytabs`
- same controller-staging broker pattern `ctlabs_ca` uses for certificates).
This role copies it from there to `keytab.dest_dir` on the slapd host
(`/etc/ldap/keytabs` by default, `0600`, owned by the slapd service user) and
points `KRB5_CLIENT_KTNAME` (the *client* keytab env var - this role is the
GSSAPI initiator, not an acceptor, so `KRB5_KTNAME` does not apply here) at it
via `/etc/default/slapd`.

Only **one** GSSAPI identity is supported per host - if multiple `dbs`
entries use `bind.method: sasl`, the first one wins.

A minimal `/etc/krb5.conf` (realm + KDCs, no sssd/pkinit) is rendered so this
works **without** `ctlabs_sssd` as a dependency. If this host also runs
`ctlabs_sssd` with the `AD` backend, that role already owns `/etc/krb5.conf`
with the same information - set `krb5.manage: false` (role var or
`ctg_facts.ctlabs_slapd.krb5.manage`) so the two roles don't fight over the
file.

| Fact                 | Description                                        | Default                 |
|----------------------|-----------------------------------------------------|--------------------------|
| `krb5.manage`        | Render `/etc/krb5.conf` from this role               | `true`                   |
| `krb5.file`          | Destination path                                     | `/etc/krb5.conf`         |
| `krb5.realm`         | Kerberos realm (uppercase)                           | `AD.CTLABS.INTERNAL`     |
| `krb5.domain`        | DNS domain for the realm                             | `ad.ctlabs.internal`     |
| `krb5.kdc`           | List of KDC (DC) hostnames                           | `[dc1.ad..., dc2.ad...]` |

Resolved the same way as `dbs`: role var (`ctlabs_slapd_krb5`) -> local fact
(`ctg_facts.ctlabs_slapd.krb5`) -> role default - set the fields you need to
override as a whole `krb5:` block, not individually.
