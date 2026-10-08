# Ansible Role `ctlabs_vault`

## Modes

The role supports four install modes via `ctlabs_vault_install_type`:

| Mode     | Description                                         |
|----------|-----------------------------------------------------|
| `cli`    | Install vault binary only — no config or service    |
| `server` | Full vault server with file storage, TLS, init      |
| `agent`  | Vault Agent with GCP auto-auth, optional cache/sink |
| `proxy`  | Vault Proxy with GCP auto-auth, cache, unix/mtls    |

The install type is resolved per host in `tasks/precheck.yml`:

1. Local fact `ctg_facts.ctlabs_vault.install_type` (authoritative — per-host)
2. `ctlabs_vault_install_type` variable (fallback only)
3. `cli` (default when neither is set)

## Ansible Tags

- `ctlabs_vault`
- `ctlabs_vault.precheck`
- `ctlabs_vault.package`
- `ctlabs_vault.config`
- `ctlabs_vault.service`
- `ctlabs_vault.init`
- `ctlabs_vault.bootstrap`

## Variables

| Variable                          | Default       | Description                                    |
|-----------------------------------|---------------|------------------------------------------------|
| `ctlabs_vault_install_type`       | `cli`         | Install mode: `cli`, `server`, `agent`, `proxy` |
| `ctlabs_vault_server_addr`        | see below     | Vault server address for agent/proxy connect |
| `ctlabs_vault_agent_gcp_role`     | `gce-role`    | GCP auth role for auto_auth                    |
| `ctlabs_vault_agent_cache`        | `false`       | Enable agent token caching                     |
| `ctlabs_vault_agent_sink`         | `true`        | Write token to `/run/vault/token`              |
| `ctlabs_vault_proxy_socktype`     | `unix`        | Proxy listener type: `unix` or `mtls`          |

### Resolution

`ctlabs_vault_server_addr` resolves in this order:

1. `ctg_facts.ctlabs_vault.address` (local fact override)
2. `ctlabs_vault_server_addr` (role default, `https://{{ ansible_default_ipv4.address }}:8200`)

On agent/proxy hosts, provide the vault server address via a local fact — e.g., if vdb1 (`192.168.99.30`) is the server:

```json
{
  "address": "https://192.168.99.30:8200"
}
```

## Local Facts

Fact file: `/etc/ansible/facts.d/ctlabs_vault.fact` (written by `tasks/facts.yml`).

```json
{
  "address"      : "https://<vault-server-ip>:8200",
  "install_type" : "server"
}
```

- `address` — vault server address for agent/proxy connect
- `install_type` — `cli`, `server`, `agent`, or `proxy`; resolved via `ctg_facts.ctlabs_vault.install_type` in precheck
- `bootstrap` — optional, `install_type: server` only: the declarative setup `bootstrap.yml` applies (engines/auth/policies/users/approle/jwt/kubernetes). See [Declarative Setup](#declarative-setup-bootstrapyml) below for its schema. File mode is `0600`, not the default, once this key is in use — it can carry real userpass passwords.

### Agent
```json
{
  "address"      : "https://<vault-server-ip>:8200",
  "install_type" : "agent"
}
```

### Proxy
```json
{
  "address"      : "https://<vault-server-ip>:8200",
  "install_type" : "proxy"
}
```

## Prechecks

Supported OS: `redhat9`, `centos9`, `debian11`, `debian12`

## Init Output & Seal-Key Recovery

On first init of a `server` vault, the role writes the init result to the
ansible repo root (delegated to localhost, mode `0400`, root-owned):

```
{{ ctg_ansible_repo_dir }}/.ctlabs_vault_init_output_{{ ansible_nodename }}.yml
```

It contains `vault_root_token` and `vault_unseal_keys_b64`. **Treat this file as our only copy of the unseal key (threshold 1) and the root token — never delete, move, or edit it.**

### What happens if it's lost

- **Vault still unsealed:** content stays accessible, but a service restart or  seal makes it **permanently sealed** — storage cannot be decrypted and  re-initializing would destroy all content (`sys/init` only runs when  `!initialized`).
- **Vault sealed:** not recoverable.
- **Rekey does NOT help:** a rekey requires a **quorum of the existing unseal  keys** to authorize (HashiCorp `operator rekey` docs). With `secret_shares = 1`,  that means the one lost key is still required. Key loss is unrecoverable by  design.

The only hard protection is redundancy: keep a second copy of the init output file off-host, use a sealed `vault-backup.py` archive (below — it embeds the keys, encrypted, and `restore-*` writes the recovered keys back to a keyring on the host so the next backup needs no key flags), or increase `secret_shares`/`secret_threshold` at init so losing one share doesn't lock the vault.

### Seal-key rotation (compromise, routine rotation)

`vault operator rekey` mints a **brand-new set of unseal keys** — zero data loss, zero downtime — and invalidates the exposed keys. This is the procedure if a seal key is ever compromised or as part of routine rotation. It requires a token with `sudo` on `sys/rekey` — the `ctlabs` userpass policy grants this (since 2026-08-28). Note: unlike key-loss, this still works because the valid holders can provide the existing single key.

```sh
vault login -method=userpass username=ctlabs password='secret123!'
vault operator rekey -init -key-shares=1 -key-threshold=1   # prints a nonce
vault operator rekey -nonce=<nonce>                          # prompts for the current key
```

The final command outputs the **new** unseal key(s) and a rekey nonce — persist the new `vault_unseal_keys_b64` into the init output file immediately, then destroy the previous records.

## Declarative Setup (`bootstrap.yml`)

After init, a `server` vault is bootstrapped from a declarative setup instead of the historical hard-coded `init.yml` steps (enable userpass, create the `ctlabs` user + policy). The role applies engines, auth methods, policies, userpass users, approle roles, jwt/oidc config, and kubernetes auth (config + role bindings) idempotently — every write is preceded by a read.

### Source of truth (`ctlabs_vault_setup`)

Resolution order (same local-facts pattern as the rest of the role):

1. Local fact `ctg_facts.ctlabs_vault.bootstrap` — the `bootstrap` key of this role's own `ctlabs_vault.fact` (`/etc/ansible/facts.d/ctlabs_vault.fact`), same file as `address`/`install_type`, same `<role_name>.fact` convention every other role uses. Authoritative, per host. **Not a separate `ctlabs_vault_setup.fact`** — an earlier version of this role used one; if you find a reference to that file elsewhere, it's stale.
2. Role default `ctlabs_vault_setup` in `defaults/main.yml` — fallback that mirrors today's behavior (enable `userpass`, user `ctlabs` / policy `ctlabs` from `ctlabs.hcl.j2`)

Omitted (not written as `{}` or `null`) when absent from the fact, same as `address`/`install_type` — a written-but-empty `bootstrap` key would shadow the role-default fallback above instead of falling through to it.

### Fact schema

```json
{
  "engines": [
    { "path": "kvv2", "type": "kv", "description": "...", "options": { "version": "2" } }
  ],
  "auth": [
    { "path": "userpass", "type": "userpass", "description": "..." },
    { "path": "approle",  "type": "approle" }
  ],
  "policies": [
    { "name": "ctlabs", "policy": "<HCL or template/file reference>", "source": "template|file|inline" }
  ],
  "users": [
    { "username": "ctlabs", "password": "secret123!", "policies": ["default", "ctlabs"], "auth_path": "userpass" }
  ],
  "approle_roles": [
    { "name": "atlantis-runner", "auth_path": "approle", "token_policies": ["cf-ci"],
      "token_ttl": "1h", "token_max_ttl": "24h", "secret_id_ttl": "24h", "secret_id_num_uses": 0,
      "secret_id_bound_cidrs": ["192.168.99.5/32"], "bind_secret_id": true }
  ],
  "jwt": { "mount": "jwt", "discovery_url": "https://.../.well-known/openid-configuration",
           "default_role": "default",
           "validation": { "host": "", "kubeconfig": "", "context": "" },
           "roles": [ { "name": "cert-vault-sync-dev", "bound_audiences": ["vault"], "user_claim": "sub",
                        "bound_subject": "system:serviceaccount:security-tools:cert-vault-sync-dev",
                        "claim_mappings": {}, "token_policies": ["cert-vault-sync-dev"], "token_ttl": 3600 } ] },
  "kubernetes": [
    { "mount": "kubernetes", "host": "https://<k8s-apiserver>:6443",
      "ca_cert": "<cluster CA PEM>", "token_reviewer_jwt": "<reviewer SA token>",
      "roles": [
        { "name": "cert-vault-sync-dev", "bound_service_account_names": ["cert-vault-sync-dev"],
          "bound_service_account_namespaces": ["security-tools"],
          "token_policies": ["cert-vault-sync-dev"], "token_ttl": "1h" }
      ]
    }
  ]
}
```

Notes:

- `policies.source` — `template` renders a role template (`template: ctlabs.hcl.j2`), `file` reads a static HCL file (path on the controller), `inline` uses `policy` verbatim.
- `engines` use Vault's API-native form: kv-v2 = `"type": "kv"` + `"options": { "version": "2" }` (the CLI's `kv-v2` alias is expanded to this; the exporter emits this form). Duration-like params (`token_ttl`, `secret_id_ttl`, ...) accept Go duration strings (`1h`) or integer seconds (`3600`).
- `auth_path` on users/roles defaults to `userpass` / `approle` when omitted. `engines`, `auth`, `policies`, `users`, `approle_roles`, `jwt`, `kubernetes` are all optional.
- `kubernetes` is a **list** of mounts (unlike `jwt`, which is a single mapping), each with its own `roles` list — one Vault install can front more than one cluster. The auth method itself (`"path": "kubernetes", "type": "kubernetes"` in `auth`) is enabled by the generic Auth Methods section above; this key only configures the mount's connection (`auth/<mount>/config`) and its per-role service-account bindings (`auth/<mount>/role/<name>`). `token_reviewer_jwt` is **write-only** (never returned on read, same as a userpass password or an OIDC signing key) — bootstrap can detect a changed `host`/`ca_cert` and re-push, but a *rotated* reviewer JWT with unchanged host/CA is not detected as drift and must be re-applied by hand.
- **Passwords are input-only**: creating a *new* user requires `password` (Vault can't read it back). Existing users get policies reconciled only — a changed `password` field has **no effect**. The bootstrap skips (with a message) creation of a new user that has no `password`.
- **Secrets never leave the host**: the root token comes from `vault_root_token` in the init output file on the controller (never written to a `.fact` file), and passwords live in the fact file / role defaults only — nothing is written back to disk by the role.
- `approle_roles` and `jwt.roles` are created when absent (404). Their parameters are set only for keys present in the fact (PUT is a full-set write, so an absent key is not clobbered). Changing parameters of an *existing* role is done via `vault-auth` / `vault write`, not by re-running bootstrap.
- `jwt.roles[].bound_subject` and `token_ttl` are written together with the rest of the role body (a role with `bound_subject` accepts *only* that subject, so it can only be created once the mount itself has a validation source — see the gate below).

### JWT: where the public keys come from

`auth/<mount>/config` accepts **exactly one** of `jwt_validation_pubkeys` / `jwks_url` / `jwks_pairs` / `oidc_discovery_url`, and any config write is a full replace (unknown keys are silently dropped — `audience` is one of them: OpenBao 2.x has no `audience` on this endpoint, audiences belong on the *role* as `bound_audiences`).

In this lab the apiserver is not a usable discovery source: `192.168.99.30:6443` is refused from the Vault host, and the data-plane IP answers `401` to anonymous `/.well-known/...`. So bootstrap fetches the JWKS **from the API node at run time** and injects it as `jwt_validation_pubkeys`:

1. **Spec** — `jwt.validation.host` / `jwt.validation.kubeconfig` / `jwt.validation.context` in the profile, if set, win outright (empty/absent = auto).
2. **Auto-detect** — scan hostvars for a node that owns a cluster: `ctlabs_rke2.server_node` (preferred), `ctlabs_k8s.master_node`, `ctlabs_kind`, `ctlabs_minikube`, `ctlabs_k3s` — so rke2/k8s/kind/k3s/minikube all work without touching the profile.
3. **Kubeconfig** — probe `ctlabs_vault_jwks['kubeconfigs']` (`/etc/rancher/rke2/rke2.yaml`, `/etc/rancher/k3s/k3s.yaml`, `/root/.kube/config`, ...) on that node; `current-context` gives the server URL plus client certificate/key.
4. **Fetch** — stage the material inline into a root-only `/run/ctlabs-jwks` dir (deleted in the next task, even on failure), `GET <server>/openid/v1/jwks`, decode `keys[*].n` (b64url, unpadded) into SPKI PEMs via the `jwks_to_pems` filter (RSA signing keys only; EdDSA/EC JWKs are skipped with a message). Reachability is delegated to the detected node — the controller never talks to the apiserver.
5. **Write** — `jwt.config.write` pushes `jwt_validation_pubkeys` when the fetch returned keys, else `oidc_discovery_url` from `jwt.discovery_url`, but **only when something actually differs** from the running config (400/404, changed key set, changed discovery URL). It never writes `audience`.
6. **Gate** — `jwt.config.ready` records whether the mount now has a validation source (fetched keys / profile discovery / read-back config). `jwt.role.create` requires it; if the cluster isn't up yet the run logs one `NOTICE` (`jwt.config.skipped`, re-run with tag `vault_rke2`) and stops — config and roles are never written half-configured.

The `until`-retried fetch (6 × 10s) tolerates an apiserver still finishing TLS bootstrapping; an exhausted wait degrades to that same NOTICE instead of a red run.

### Exporting an existing setup — `vault-export.py`

`vault-export.py` (installed to `/usr/sbin/vault-export.py`) dumps the *configuration* of a live Vault into the `bootstrap` key of the fact file above, so a brand-new host can reproduce it after a fresh init — **without the seal keys**. It uses the Vault HTTP API directly (urlib/stdlib only, no `vault` binary, no third-party deps):

```sh
vault-export.py --addr https://ansible.ctlabs.internal:8200 --token "$(cat .ctlabs_vault_init_output_*.yml ...)" \
  --insecure --out /etc/ansible/facts.d/ctlabs_vault.fact
```

Flags: `--addr` (or `VAULT_ADDR`), `--token` (or `VAULT_TOKEN`), `--out` (default stdout; mode `0600`), `--insecure` (self-signed lab CA), `--ca-cert <ca.crt>`.

**`--out` merges into the `bootstrap` key, it does not overwrite the file** — any other keys already there (`address`, `install_type`) are preserved. Refuses to run (loud `SystemExit`, not a silent clobber) if `--out` already exists and isn't valid JSON.

Exports: engines + auth methods (token/ system/ identity/ skipped), ACL policies (inline HCL, default/root skipped), userpass users (name + policies only), approle roles (incl. `secret_id_ttl` / `secret_id_bound_cidrs` / `token_ttl` / `secret_id_num_uses`), jwt/oidc mount config + roles, and an `identity_oidc` inventory marker (see below).

**Tradeoff (documented):** this is *config-restore, not storage-restore*. userpass passwords and KV/secret data are NOT restored by it (Vault cannot read passwords back; KV data lives in storage). For full data-level restore use `vault-backup.py` sealed archives (below). The exported user entries carry no `password` — add them to the fact file before bootstrap on the new host.

#### `identity/oidc/*` (GCP Workload Identity Federation) is deliberately NOT restored by config-restore

This is the one piece of Vault configuration that **cannot** be reproduced from the API, so the exporter emits an inventory marker plus a loud `WARNING` instead of a lossy "reproduction" that would look complete. Verified against a live Vault (2.1.1, RS256):

1. **An OIDC signing key's private half is write-only.** `identity/oidc/key/<name>` read-back returns only `algorithm` / `rotation_period` / `verification_ttl` / `allowed_client_ids` — no key material — and the JWKS endpoint exposes only `n` + `e`. A bootstrapped vault would sign with a **different key** than GCP was configured to trust, breaking a working WIF setup.
2. **`identity/oidc/role/<name>` read-back is filtered** to `client_id`, `key`, `template`, `ttl`. `token_policies`, `bound_claims`, `user_claim` and `allowed_redirect_uris` are accepted on write but never returned, so they cannot be carried across.
3. **The key's client-ID/role restriction is enforced but invisible on read** (token minting is refused for a role the key does not permit), so re-creating the key could silently widen or narrow it.

Consequences:

| Path | `identity/oidc/*` | OIDC signing key |
| --- | --- | --- |
| `vault-backup.py` storage archive | **restored** (whole `file` storage tree is archived) | **preserved byte-for-byte** |
| `vault-export.py` + `bootstrap.yml` | not restored (marker + warning only) | cannot be reproduced — new key |

So: restore WIF from a `vault-backup.py` archive, or re-run `ctlabs-terraform/scripts/vault_oidc_setup.py` against the target Vault. That script is the owner of this content and is idempotent for the same key/role names. `bootstrap.yml` prints a `NOTICE` when a Vault has no OIDC issuer, so a WIF-less lab is never silently mistaken for a configured one.

## Backup & Restore — sealed `.vback` archives (`vault-backup.py`)

`vault-backup.py` (installed to `/usr/sbin/vault-backup.py`) builds a **single, self-contained, encrypted** archive of the Vault *storage* — including the unseal key(s) + root token it needs to come back up on restore:

```
vault-(snap|full)-<ts>.vback
  = magic + salt + Fernet( tar.gz { ctlabs-restore-meta.json, data/, [config/] } )
```

- **Fernet** (AES-128-CBC + HMAC-SHA256, authenticated) keyed by **PBKDF2-HMAC-SHA256** (300k iterations, random salt). Needs `python3-cryptography`.
- **Passphrase is never stored**: provide it via `VAULT_BACKUP_PASSPHRASE`, `--passphrase-file <mode-0600-file>`, or an interactive prompt — **never** on the command line. Keep it out-of-band (password manager / custodian). Without it an archive yields nothing (confidentiality) and any tampering is detected (authenticity).
- The controller keyring (`{{ ctg_ansible_repo_dir }}/.ctlabs_vault_init_output_<node>.yml`) is the offline fallback copy of the keys and feeds them into the backup via `--keys-file`.
- `restore-*` **persists the recovered keys** to a keyring (below), and `backup-*` auto-discovers it — so a restored vault can be backed up again with no key flags.

### Recovered-key keyring

A restore replaces the storage, so the **only** keys that can ever unlock that vault afterwards are the ones inside the archive. If nothing on disk holds them, the archive becomes a single point of failure — and `RETENTION_DAYS` prunes old archives. `restore-*` therefore writes the recovered keyring out: a `0700` dir holding a random 32-char passphrase (`0600`) plus the symmetric-gpg ciphertext of the keyring (`0600`).

| Path | Mode | Contents |
|------|------|----------|
| `/etc/vault-backup/` | `0700` | dir |
| `/etc/vault-backup/passphrase` | `0600` | random 32-char gpg passphrase |
| `/etc/vault-backup/keys.gpg` | `0600` | gpg-symmetric ciphertext of the keyring |

**The mechanism is ctlabs-tools' (`ctlabs_tools/vault/vault_login.py`); the namespace deliberately is not.** That tool treats `~/.ctlabs_vault/` as a *disposable session cache* — `vault-login clear` deletes `.vault_key`, and `vault-login user|oidc|approle` overwrites it with a fresh random value on every login. Storing the unseal key + root token there would mean a routine logout destroys the only copy of the keys and silently bricks the vault on its next seal. Keep the two lifecycles apart. `test_backup_keyring_never_shares_ctlabs_tools_session_cache` pins this.

| Target path | Codec |
|------|-------|
| any `.gpg` path (default `/etc/vault-backup/keys.gpg`) | gpg-symmetric; passphrase in `<dir>/passphrase` |
| any other path (e.g. the controller init-output file) | plaintext `0400`, init-output YAML shape |

- **The codec is inferred from the `.gpg` suffix**, so one run can write both: `--keyring-out /etc/vault-backup/keys.gpg --keyring-out {{ ctg_ansible_repo_dir }}/.ctlabs_vault_init_output_<node>.yml`. The plaintext form is the exact `init.yml` shape, so `bootstrap.yml` (`from_yaml`) and `--keys-file` read the same file.
- The passphrase goes to gpg via `--passphrase-file`, **never argv** (`ps` is world-readable). Unlike the ctlabs-tools implementation, which passes `--passphrase <pw>` on both sides.
- This protects the keys from casual disclosure (`cat`/`grep`/diff/plaintext backup of a config dir) — **not** from root on the host, which can read the passphrase file.
- The keyring passphrase is **independent** of the archive's Fernet passphrase; neither is derived from the other.
- Writing the keyring happens **after** the restore is proven unsealed with a valid root token, so a failed restore never leaves a keyring that doesn't match the running vault. An existing keyring that differs is copied to `<path>.pre-<ts>` first — never silently clobbered, since it may be the only working keyring for a vault you did not mean to replace.
- `gnupg` (`gnupg2` on RedHat) is installed by the role for this. A `.gpg` target with no gpg binary is a hard error, not a silent plaintext fallback — use a non-`.gpg` `--keyring-out` if you want plaintext.
- Rekey after a restore invalidates the on-disk keyring; the next `backup-*` fails loudly at the root-token verification and names the stale key source.

### Usage

```sh
# on the vault host
vault-backup.py backup-full \
  --passphrase-file /etc/vault-backup.pw          # or VAULT_BACKUP_PASSPHRASE
# keys are auto-discovered from /etc/vault-backup/keys.gpg (or --keys-file)
# -> /var/backups/vault/vault-full-<ts>.vback (mode 0600)

vault-backup.py restore-full /var/backups/vault/vault-full-<ts>.vback \
  --passphrase-file /etc/vault-backup.pw          # prompts YES confirmation
# -> storage replaced, unsealed, root token verified, keyring written
#    -> the next backup-full needs no key flags at all

# co-located controller+vault: also refresh the file bootstrap.yml reads
vault-backup.py restore-full <archive> \
  --keyring-out /etc/vault-backup/keys.gpg \
  --keyring-out {{ ctg_ansible_repo_dir }}/.ctlabs_vault_init_output_{{ ansible_nodename }}.yml \
  --passphrase-file /etc/vault-backup.pw
```


Subcommands: `backup-snap` / `backup-full` (data / data+config), `restore-snap` / `restore-full`. Common flags: `--keys-file`, `--passphrase-file`, `--addr` (default `api_addr` from `vault.hcl`), `--ca-cert`, `--data-dir`, `--config-dir`, `--out-dir`, `--service`; backup also `--keyring` (keyring to read, first existing wins) / `--force` / `--no-unseal`; restore also `--keyring-out` (repeatable) / `--no-keyring` / `--yes`.

### Scheduled backups (`vault-backup.timer`)

`tasks/timer.yml` installs `vault-backup.service` + `vault-backup.timer`, so backups run unattended daily at **03:17** (±15 min random delay) instead of depending on a human remembering. `Persistent=true`, so if the box was off at 03:17 the backup runs at the next boot rather than being silently skipped for the day.

```sh
systemctl list-timers vault-backup.timer     # when it next fires
systemctl start vault-backup.service          # run one now, same code path
tail -f /var/log/vault-backup.log
```

Defaults live under `ctlabs_vault.defaults.config.backup` (`on_calendar`, `command`, `out_dir`, `persistent`, …). `command: backup-full` (not `backup-snap`) so each archive also carries the config dir — a `snap` restore comes back with no TLS cert.

**The archive passphrase is required and is never generated by this role.** Supply it as `ctlabs_vault.defaults.config.backup.passphrase` (written to `/etc/vault-backup.pw`, mode `0400`, `no_log` so it never hits the Ansible log) or create that file yourself. If it is absent the role prints a `NOTICE` and **skips** installing the timer rather than failing — same skip idiom as `bootstrap.yml`. Rationale: a passphrase invented here and never handed to anyone makes every archive permanently unreadable. That is the same single-owner-secret trap as the keyring above, so the role refuses to walk into it. The passphrase is *not* the keyring passphrase (`/etc/vault-backup/passphrase`) — two different secrets for two different jobs.

**Escrow it off-host together with the archives.** An archive plus its passphrase stored in the same place is the same place.

> **Do not add `Requires=vault.service` to the backup unit.** `vault-backup.py` stops Vault to take a consistent storage snapshot, so a hard dependency makes that explicit stop propagate and systemd cancels the job. Verified on this lab: the unit dies with `Result: signal` / `signal=TERM`, **no archive is written**, and Vault is left `deactivating` (i.e. down and sealed, needing a manual unseal). `After=` is the correct and sufficient ordering. Pinned by `test_backup_service_does_not_require_vault_service`.

### Safety properties

- **Refuses to stop the vault when it can't unseal it afterwards** (e.g. running but no key available) unless `--force` — this removes the "service restart with lost key = permanently sealed" trap.
- After every stop/start it **auto-unseals** with the embedded key and **verifies the root token** (`auth/token/lookup-self`) — proving on every run that the keyring still matches the vault (catches post-rekey staleness).
- **Key source precedence**: `--keys-file` → `VAULT_BACKUP_UNSEAL_KEYS`/`VAULT_BACKUP_ROOT_TOKEN` → first existing path in `--keyring` (default `~/.ctlabs_vault/.vault_keys.gpg`). With none of them it refuses rather than sealing the vault.
- **Restore verifies the archive (magic + auth) before touching anything**, moves the existing data dir aside (`.pre-<ts>`, newest kept) instead of deleting, extracts into a staging dir, swaps, starts, unseals, verifies — and only then writes the recovered keyring. Bad passphrase or tampering aborts with a clean error — nothing is touched.
- Archives are world-unreadable (mode 0600). Old archives are pruned after `RETENTION_DAYS`.

### Migration note

Legacy backups from the old script are plaintext `.tar.gz` (e.g. `vault-snap-*.tar.gz`) and contain **no keys** — unusable for restore without the keyring, and sensitive. After you have a verified `.vback` from the same vault, purge the old `.tar.gz` files. Never keep an unencrypted archive alongside a `.vback`.

### Restore checklist (e.g. onto a fresh host)

1. Install/run the role so `/usr/sbin/vault-backup.py` exists (fresh hosts re-init or restore directly).
2. Copy the `.vback` **and** the passphrase (separately) to the host; `systemctl stop vault` is handled by the script.
3. `vault-backup.py restore-full <archive> ...` — the script replaces the storage, restarts the service, unseals, verifies the root token and writes the recovered keyring. **Back that keyring up off-host**: it plus the passphrase is the only way back in.
