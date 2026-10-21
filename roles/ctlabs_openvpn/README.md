# Ansible Role `ctlabs_openvpn`

Configures point-to-point OpenVPN tunnels (static-key / site-to-site) between lab nodes and remote cloud gateways (e.g. `gcp-gw` ↔ `ro1`).

The shared static secret is generated once on the **ansible controller** (`delegate_to: localhost`, stored under `/etc/openvpn/<project>_<key_name>.key`) and distributed to each endpoint, ensuring consistent keys across separate plays and remote hosts.

## Ansible Tags

- `ctlabs_openvpn`
- `ctlabs_openvpn.precheck`
- `ctlabs_openvpn.package`
- `ctlabs_openvpn.config`
- `ctlabs_openvpn.service`
- `ctlabs_openvpn.facts`

## Supported Operating Systems

- `centos9`, `redhat9`
- `debian11`, `debian12`
- `ubuntu22`, `ubuntu24`

## Configuration

| Variable                                      | Default            | Description                                              |
|-----------------------------------------------|--------------------|----------------------------------------------------------|
| `ctlabs_openvpn.defaults.config.dir`          | `/etc/openvpn`     | Base OpenVPN directory on node                          |
| `ctlabs_openvpn.defaults.config.server.dir`   | `/etc/openvpn/server` | Server configuration directory                         |
| `ctlabs_openvpn.defaults.config.server.file`  | `/etc/openvpn/server/server.conf` | Server configuration file               |
| `ctlabs_openvpn.defaults.config.server.key`   | `/etc/openvpn/server/ovpn.key`   | Server shared secret file               |
| `ctlabs_openvpn.defaults.config.client.dir`   | `/etc/openvpn/client` | Client configuration directory                         |
| `ctlabs_openvpn.defaults.config.client.file`  | `/etc/openvpn/client/client.conf` | Client configuration file               |
| `ctlabs_openvpn.defaults.config.client.key`   | `/etc/openvpn/client/ovpn.key`   | Client shared secret file               |
| `ctlabs_openvpn.defaults.config.controller_key_dir` | `/etc/openvpn` | Directory on controller storing generated shared keys |
| `ctlabs_openvpn.defaults.config.key_name`     | `ovpn`             | Default key identifier                                  |
| `ctlabs_openvpn.defaults.config.port`         | `1194`             | Default UDP/TCP port                                    |
| `ctlabs_openvpn.defaults.config.proto`        | `udp`              | Default protocol (`udp` or `tcp`)                       |
| `ctlabs_openvpn.defaults.config.dev`          | `tun0`             | Tun device name                                         |
| `ctlabs_openvpn.defaults.config.cipher`       | `AES-256-CBC`      | Encryption cipher                                       |
| `ctlabs_openvpn.defaults.config.auth`         | `SHA512`           | Message authentication digest                           |
| `ctlabs_openvpn.defaults.config.forward`      | `true`             | Enable IPv4 packet forwarding (`net.ipv4.ip_forward=1`) |

## Local Facts

Local facts are generated in `/etc/ansible/facts.d/ctlabs_openvpn.fact`:

```json
{
  "type": "server",
  "server_ip": "10.8.15.1",
  "client_ip": "10.8.15.2",
  "dev": "tun0",
  "port": 1194
}
```

For client nodes, `remote` specifies the remote public or reachable endpoint:

```json
{
  "type": "client",
  "server_ip": "10.8.15.1",
  "client_ip": "10.8.15.2",
  "remote": "35.200.10.7",
  "dev": "tun0",
  "port": 1194
}
```

## Behavior & Design

- **Static Key Generation & Distribution**:
  - The shared key is generated once on the controller (`openvpn --genkey secret <path>`) under `/etc/openvpn/<project>_<key_name>.key`.
  - Guarded by `stat`: if the key file already exists, it is reused. This prevents re-generating mismatched keys when endpoints run in separate plays or during partial playbook reruns.
  - The key is copied to `/etc/openvpn/server/ovpn.key` on server nodes and `/etc/openvpn/client/ovpn.key` on client nodes with mode `0600`.
- **IP Forwarding**:
  - Sets `net.ipv4.ip_forward = 1` via `ansible.posix.sysctl` when `forward: true`.
- **Services**:
  - Manages `openvpn-server@server.service` or `openvpn-client@client.service` via systemd.

## Tests

```sh
PATH=/usr/local/bin:$PATH pytest -sv roles/ctlabs_openvpn/tests/ --rootdir=roles
```
