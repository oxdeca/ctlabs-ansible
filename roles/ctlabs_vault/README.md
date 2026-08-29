# Ansible Role `ctlabs_vault`

## Modes

The role supports four modes via `CTLABS_VAULT_ROLE`:

| Mode     | Description                                         |
|----------|-----------------------------------------------------|
| `cli`    | Install vault binary only — no config or service    |
| `server` | Full vault server with file storage, TLS, init      |
| `agent`  | Vault Agent with GCP auto-auth, optional cache/sink |
| `proxy`  | Vault Proxy with GCP auto-auth, cache, unix/mtls    |

## Ansible Tags

- `ctlabs_vault`
- `ctlabs_vault.precheck`
- `ctlabs_vault.package`
- `ctlabs_vault.config`
- `ctlabs_vault.service`
- `ctlabs_vault.init`

## Variables

| Variable                          | Default       | Description                                    |
|-----------------------------------|---------------|------------------------------------------------|
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

### Agent
```json
{
  "address": "https://<vault-server-ip>:8200"
}
```

### Proxy
```json
{
  "address": "https://<vault-server-ip>:8200"
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

The only hard protection is redundancy: keep a second copy of the init output file off-host, or increase `secret_shares`/`secret_threshold` at init so losing one share doesn't lock the vault.

### Seal-key rotation (compromise, routine rotation)

`vault operator rekey` mints a **brand-new set of unseal keys** — zero data loss, zero downtime — and invalidates the exposed keys. This is the procedure if a seal key is ever compromised or as part of routine rotation. It requires a token with `sudo` on `sys/rekey` — the `ctlabs` userpass policy grants this (since 2026-08-28). Note: unlike key-loss, this still works because the valid holders can provide the existing single key.

```sh
vault login -method=userpass username=ctlabs password='secret123!'
vault operator rekey -init -key-shares=1 -key-threshold=1   # prints a nonce
vault operator rekey -nonce=<nonce>                          # prompts for the current key
```

The final command outputs the **new** unseal key(s) and a rekey nonce — persist the new `vault_unseal_keys_b64` into the init output file immediately, then destroy the previous records.