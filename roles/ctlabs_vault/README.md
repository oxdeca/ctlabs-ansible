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
