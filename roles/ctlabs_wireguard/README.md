# Ansible Role `ctlabs_wireguard`

Configures point-to-point WireGuard tunnels between lab nodes and remote cloud gateways (e.g. `gcp-gw` ↔ `ro1`).

X25519 keypairs for both endpoints (`server.key`/`server.pub` and `client.key`/`client.pub`) are generated on the **ansible controller** via a Python cryptographic helper (`files/create_wireguard_keys.py`), stored in `/etc/wireguard/<project>_<key_name>/`, and templated into `/etc/wireguard/<dev>.conf`. This eliminates manual key exchange across separate plays or remote cloud VMs.

## Ansible Tags

- `ctlabs_wireguard`
- `ctlabs_wireguard.precheck`
- `ctlabs_wireguard.package`
- `ctlabs_wireguard.config`
- `ctlabs_wireguard.service`
- `ctlabs_wireguard.facts`

## Supported Operating Systems

- `redhat9`, `centos9`
- `debian11`, `debian12`
- `ubuntu22`, `ubuntu24`

## Configuration

| Variable                                        | Default              | Description                                                    |
|-------------------------------------------------|----------------------|----------------------------------------------------------------|
| `ctlabs_wireguard.defaults.config.dir`          | `/etc/wireguard`     | Base WireGuard config directory on node                        |
| `ctlabs_wireguard.defaults.config.template`     | `wireguard.conf.j2`  | WireGuard interface config template                            |
| `ctlabs_wireguard.defaults.config.dev`          | `wg0`                | WireGuard network interface name                               |
| `ctlabs_wireguard.defaults.config.port`         | `51820`              | UDP listen port (server)                                       |
| `ctlabs_wireguard.defaults.config.controller_key_dir` | `/etc/wireguard` | Controller directory for generated tunnel keypairs             |
| `ctlabs_wireguard.defaults.config.key_name`     | `wg0`                | Key/tunnel identifier                                          |
| `ctlabs_wireguard.defaults.config.allowed_ips`   | `0.0.0.0/0`          | AllowedIPs for cryptokey routing                               |
| `ctlabs_wireguard.defaults.config.table`         | `off`                | Routing table integration (`off` prevents clobbering FRR/BGP)  |
| `ctlabs_wireguard.defaults.config.persistent_keepalive` | `25`        | Keepalive interval in seconds (client endpoint)                |
| `ctlabs_wireguard.defaults.config.forward`      | `true`               | Enable IPv4 forwarding (`net.ipv4.ip_forward=1`)               |

## Local Facts

Local facts are generated in `/etc/ansible/facts.d/ctlabs_wireguard.fact`:

```json
{
  "type": "server",
  "server_ip": "10.8.15.1",
  "client_ip": "10.8.15.2",
  "dev": "wg0",
  "port": 51820
}
```

For client nodes, `remote` specifies the remote public/reachable server endpoint:

```json
{
  "type": "client",
  "server_ip": "10.8.15.1",
  "client_ip": "10.8.15.2",
  "remote": "35.200.10.7",
  "dev": "wg0",
  "port": 51820
}
```

## Behavior & Design

- **Asymmetric Keypair Generation**:
  - The controller generates `server.key`, `server.pub`, `client.key`, and `client.pub` once under `/etc/wireguard/<project>_<key_name>/` using `files/create_wireguard_keys.py` (Python `cryptography` X25519).
  - Server config receives `server.key` (PrivateKey) and `client.pub` (PublicKey).
  - Client config receives `client.key` (PrivateKey) and `server.pub` (PublicKey).
  - Keys are guarded by existence checks and never regenerated on playbook reruns.
- **Routing & Table Integration**:
  - `Table = off` ensures `wg-quick` configures the interface and IP without injecting kernel routes that would interfere with FRR BGP or default gateway routes.
  - `AllowedIPs = 0.0.0.0/0` enables cryptokey routing for all prefixes routed through the tunnel by BGP.
- **Service**:
  - Manages `wg-quick@<dev>.service` via systemd.

## Tests

```sh
PATH=/usr/local/bin:$PATH pytest -sv roles/ctlabs_wireguard/tests/ --rootdir=roles
```
