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
/root/ctlabs-ansible/.ctlabs_vault_init_output_{{ ansible_nodename }}.yml
```

It contains `vault_root_token` and `vault_unseal_keys_b64`. **Treat this file as our only copy of the unseal key (threshold 1) and the root token — never delete, move, or edit it.**

### What happens if it's lost

- **Vault still unsealed:** content stays accessible, but a service restart or  seal makes it **permanently sealed** — storage cannot be decrypted and  re-initializing would destroy all content (`sys/init` only runs when  `!initialized`).
- **Vault sealed:** not recoverable.
- **Rekey does NOT help:** a rekey requires a **quorum of the existing unseal  keys** to authorize (HashiCorp `operator rekey` docs). With `secret_shares = 1`,  that means the one lost key is still required. Key loss is unrecoverable by  design.

The only hard protection is redundancy: keep a second copy of the init output file off-host, use a sealed `vault-backup.py` archive (below — it embeds the keys, encrypted), or increase `secret_shares`/`secret_threshold` at init so losing one share doesn't lock the vault.

### Seal-key rotation (compromise, routine rotation)

`vault operator rekey` mints a **brand-new set of unseal keys** — zero data loss, zero downtime — and invalidates the exposed keys. This is the procedure if a seal key is ever compromised or as part of routine rotation. It requires a token with `sudo` on `sys/rekey` — the `ctlabs` userpass policy grants this (since 2026-08-28). Note: unlike key-loss, this still works because the valid holders can provide the existing single key.

```sh
vault login -method=userpass username=ctlabs password='secret123!'
vault operator rekey -init -key-shares=1 -key-threshold=1   # prints a nonce
vault operator rekey -nonce=<nonce>                          # prompts for the current key
```

The final command outputs the **new** unseal key(s) and a rekey nonce — persist the new `vault_unseal_keys_b64` into the init output file immediately, then destroy the previous records.

## Declarative Setup (`bootstrap.yml`)

After init, a `server` vault is bootstrapped from a declarative setup instead of the historical hard-coded `init.yml` steps (enable userpass, create the `ctlabs` user + policy). The role applies engines, auth methods, policies, userpass users, approle roles and jwt/oidc config idempotently — every write is preceded by a read.

### Source of truth (`ctlabs_vault_setup`)

Resolution order (same local-facts pattern as the rest of the role):

1. Local fact `ctg_facts.ctlabs_vault_setup` (file `/etc/ansible/facts.d/ctlabs_vault_setup.fact`) — authoritative, per host
2. Role default `ctlabs_vault_setup` in `defaults/main.yml` — fallback that mirrors today's behavior (enable `userpass`, user `ctlabs` / policy `ctlabs` from `ctlabs.hcl.j2`)

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
           "roles": [ { "name": "default", "bound_audiences": ["..."], "user_claim": "...",
                        "claim_mappings": {}, "token_policies": [] } ] }
}
```

Notes:

- `policies.source` — `template` renders a role template (`template: ctlabs.hcl.j2`), `file` reads a static HCL file (path on the controller), `inline` uses `policy` verbatim.
- `engines` use Vault's API-native form: kv-v2 = `"type": "kv"` + `"options": { "version": "2" }` (the CLI's `kv-v2` alias is expanded to this; the exporter emits this form). Duration-like params (`token_ttl`, `secret_id_ttl`, ...) accept Go duration strings (`1h`) or integer seconds (`3600`).
- `auth_path` on users/roles defaults to `userpass` / `approle` when omitted. `engines`, `auth`, `policies`, `users`, `approle_roles`, `jwt` are all optional.
- **Passwords are input-only**: creating a *new* user requires `password` (Vault can't read it back). Existing users get policies reconciled only — a changed `password` field has **no effect**. The bootstrap skips (with a message) creation of a new user that has no `password`.
- **Secrets never leave the host**: the root token comes from `vault_root_token` in the init output file on the controller (never written to a `.fact` file), and passwords live in the fact file / role defaults only — nothing is written back to disk by the role.
- `approle_roles` and `jwt.roles` are created when absent (404). Their parameters are set only for keys present in the fact (PUT is a full-set write, so an absent key is not clobbered). Changing parameters of an *existing* role is done via `vault-auth` / `vault write`, not by re-running bootstrap.

### Exporting an existing setup — `vault-export.py`

`vault-export.py` (installed to `/usr/sbin/vault-export.py`) dumps the *configuration* of a live Vault into the fact file above, so a brand-new host can reproduce it after a fresh init — **without the seal keys**. It uses the Vault HTTP API directly (urlib/stdlib only, no `vault` binary, no third-party deps):

```sh
vault-export.py --addr https://ansible.ctlabs.internal:8200 --token "$(cat .ctlabs_vault_init_output_*.yml ...)" \
  --insecure --out /etc/ansible/facts.d/ctlabs_vault_setup.fact
```

Flags: `--addr` (or `VAULT_ADDR`), `--token` (or `VAULT_TOKEN`), `--out` (default stdout; mode `0600`), `--insecure` (self-signed lab CA), `--ca-cert <ca.crt>`.

Exports: engines + auth methods (token/ system/ identity/ skipped), ACL policies (inline HCL, default/root skipped), userpass users (name + policies only), approle roles (incl. `secret_id_ttl` / `secret_id_bound_cidrs` / `token_ttl` / `secret_id_num_uses`), jwt/oidc mount config + roles.

**Tradeoff (documented):** this is *config-restore, not storage-restore*. userpass passwords and KV/secret data are NOT restored by it (Vault cannot read passwords back; KV data lives in storage). For full data-level restore use `vault-backup.py` sealed archives (below). The exported user entries carry no `password` — add them to the fact file before bootstrap on the new host.

## Backup & Restore — sealed `.vback` archives (`vault-backup.py`)

`vault-backup.py` (installed to `/usr/sbin/vault-backup.py`) builds a **single, self-contained, encrypted** archive of the Vault *storage* — including the unseal key(s) + root token it needs to come back up on restore:

```
vault-(snap|full)-<ts>.vback
  = magic + salt + Fernet( tar.gz { ctlabs-restore-meta.json, data/, [config/] } )
```

- **Fernet** (AES-128-CBC + HMAC-SHA256, authenticated) keyed by **PBKDF2-HMAC-SHA256** (300k iterations, random salt). Needs `python3-cryptography`.
- **Passphrase is never stored**: provide it via `VAULT_BACKUP_PASSPHRASE`, `--passphrase-file <mode-0600-file>`, or an interactive prompt — **never** on the command line. Keep it out-of-band (password manager / custodian). Without it an archive yields nothing (confidentiality) and any tampering is detected (authenticity).
- The controller keyring (`/root/ctlabs-ansible/.ctlabs_vault_init_output_<node>.yml`) is the offline fallback copy of the keys and feeds them into the backup via `--keys-file`.

### Usage

```sh
# on the vault host
vault-backup.py backup-full \
  --keys-file /path/to/.ctlabs_vault_init_output_<node>.yml \
  --passphrase-file /etc/vault-backup.pw          # or VAULT_BACKUP_PASSPHRASE
# -> /var/backups/vault/vault-full-<ts>.vback (mode 0600)

vault-backup.py restore-full /var/backups/vault/vault-full-<ts>.vback \
  --passphrase-file /etc/vault-backup.pw          # prompts YES confirmation
```

Subcommands: `backup-snap` / `backup-full` (data / data+config), `restore-snap` / `restore-full`. Common flags: `--keys-file`, `--passphrase-file`, `--addr` (default `api_addr` from `vault.hcl`), `--ca-cert`, `--data-dir`, `--config-dir`, `--out-dir`, `--service`; backup also `--force` / `--no-unseal`; restore also `--yes`.

### Safety properties

- **Refuses to stop the vault when it can't unseal it afterwards** (e.g. running but no key available) unless `--force` — this removes the "service restart with lost key = permanently sealed" trap.
- After every stop/start it **auto-unseals** with the embedded key and **verifies the root token** (`auth/token/lookup-self`) — proving on every run that the keyring still matches the vault (catches post-rekey staleness).
- **Restore verifies the archive (magic + auth) before touching anything**, moves the existing data dir aside (`.pre-<ts>`, newest kept) instead of deleting, extracts into a staging dir, swaps, starts, and unseals. Bad passphrase or tampering aborts with a clean error — nothing is touched.
- Archives are world-unreadable (mode 0600). Old archives are pruned after `RETENTION_DAYS`.

### Migration note

Legacy backups from the old script are plaintext `.tar.gz` (e.g. `vault-snap-*.tar.gz`) and contain **no keys** — unusable for restore without the keyring, and sensitive. After you have a verified `.vback` from the same vault, purge the old `.tar.gz` files. Never keep an unencrypted archive alongside a `.vback`.

### Restore checklist (e.g. onto a fresh host)

1. Install/run the role so `/usr/sbin/vault-backup.py` exists (fresh hosts re-init or restore directly).
2. Copy the `.vback` **and** the passphrase (separately) to the host; `systemctl stop vault` is handled by the script.
3. `vault-backup.py restore-full <archive> ...` — the script replaces the storage, restarts the service and unseals; verify with the embedded root token.
