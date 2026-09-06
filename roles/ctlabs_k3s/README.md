# Ansible Role `ctlabs_k3s`

Sets up a single- or multi-node k3s cluster.

## Node Roles

| Role      | Description                                                        |
|-----------|--------------------------------------------------------------------|
| `server`  | Bootstrap node — starts the cluster with `--cluster-init`          |
| `control` | Additional control plane node — joins server, runs `rke2 server`  |
| `worker`  | Data plane node — joins server, runs `k3s agent`                  |

## Ansible Tags

| Tag           | Targets                        |
|---------------|--------------------------------|
| `k3s`         | all k3s nodes                  |
| `k3s-server`  | bootstrap server only          |
| `k3s-control` | additional control plane nodes |
| `k3s-worker`  | worker/data plane nodes        |

## Prechecks

- OS: debian11, debian12, centos8, centos9
- Virt: kvm

## Local Facts

### Server (bootstrap)

```json
{
  "role"      : "server",
  "server_url": "https://k3s1.ctlabs.internal:6443",
  "ingress"   : {
    "type"    : "gateway_api",
    "provider": "traefik"
  }
}
```

### Control plane node

```json
{
  "role"       : "control",
  "server_node": "k3s1",
  "server_url" : "https://k3s1.ctlabs.internal:6443"
}
```

### Worker node

```json
{
  "role"       : "worker",
  "server_node": "k3s1",
  "server_url" : "https://k3s1.ctlabs.internal:6443"
}
```

## Ingress Options

| Type          | Provider        | Notes                                      |
|---------------|-----------------|--------------------------------------------|
| `gateway_api` | `traefik`       | Default — GatewayClass via Helm            |
| `gateway_api` | `envoy-gateway` | Envoy Gateway CRDs + controller            |
| `ingress`     | `nginx`         | nginx-ingress via manifest                 |

Full ingress facts example (server with Traefik):

```json
{
  "role"   : "server",
  "ingress": {
    "type"    : "gateway_api",
    "provider": "traefik"
  }
}
```

## setup_profiles.yml Example

```yaml
k3s:
  k3s1:
    role   : server
    ingress:
      type    : gateway_api
      provider: traefik
  k3s2:
    role       : control
    server_node: k3s1
    server_url : "https://k3s1.ctlabs.internal:6443"
  k3s3:
    role       : control
    server_node: k3s1
    server_url : "https://k3s1.ctlabs.internal:6443"
  k3s4:
    role       : worker
    server_node: k3s1
    server_url : "https://k3s1.ctlabs.internal:6443"
```
