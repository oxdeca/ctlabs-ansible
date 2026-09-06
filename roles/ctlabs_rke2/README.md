# Ansible Role `ctlabs_rke2`

Sets up a single- or multi-node RKE2 cluster with ArgoCD.

## Node Roles

| Role      | Description                                                              |
|-----------|--------------------------------------------------------------------------|
| `server`  | Bootstrap node — starts the cluster                                      |
| `control` | Additional control plane node — joins server, runs `rke2 server` via sysconfig |
| `worker`  | Data plane node — joins server, runs `rke2 agent`                        |

## Ansible Tags

| Tag            | Targets                        |
|----------------|--------------------------------|
| `rke2`         | all rke2 nodes                 |
| `rke2-server`  | bootstrap server only          |
| `rke2-control` | additional control plane nodes |
| `rke2-worker`  | worker/data plane nodes        |

## Prechecks

- OS: debian11, debian12, centos8, centos9, redhat9
- Virt: kvm

## Configuration

| Variable                                            | Default                  | Description                                         |
|-----------------------------------------------------|--------------------------|-----------------------------------------------------|
| `versions.rke2`                                     | `1.33.3`                 | RKE2 version                                        |
| `versions.helm`                                     | `3.16.1`                 | Helm version                                        |
| `versions.traefik`                                  | `40.0.0`                 | Traefik Helm chart version                          |
| `versions.gateway_api`                              | `1.5.0`                  | Gateway API CRDs version                            |
| `versions.envoy`                                    | `1.0.1`                  | Envoy Gateway version                               |
| `ctlabs_rke2.defaults.ingress.traefik.host_network` | `false`                  | Bind Traefik directly to node IP                    |
| `ctlabs_rke2.defaults.ingress.traefik.service_type` | `ClusterIP`              | Traefik service type                                |
| `ctlabs_rke2.defaults.argocd.host`                  | `argocd.ctlabs.internal` | ArgoCD hostname                                     |
| `ctlabs_rke2.defaults.config.ingress.type`          | `gateway_api`            | Ingress type (`ingress`, `gateway_api`)             |
| `ctlabs_rke2.defaults.config.ingress.provider`      | `traefik`                | Provider (`traefik`, `nginx`, `envoy-gateway`)      |

## Local Facts

### Server (bootstrap)

```json
{
  "role"      : "server",
  "server_url": "https://rke21.ctlabs.internal:9345",
  "ingress"   : {
    "type"    : "gateway_api",
    "provider": "traefik",
    "traefik" : {
      "host_network": true,
      "service_type": "ClusterIP"
    }
  }
}
```

### Control plane node

```json
{
  "role"       : "control",
  "server_node": "rke21",
  "server_url" : "https://rke21.ctlabs.internal:9345"
}
```

### Worker node

```json
{
  "role"       : "worker",
  "server_node": "rke21",
  "server_url" : "https://rke21.ctlabs.internal:9345"
}
```

## Ingress Options

| Type          | Provider        | Notes                                              |
|---------------|-----------------|----------------------------------------------------|
| `gateway_api` | `traefik`       | Default — Traefik via Helm, hostNetwork or LB mode |
| `gateway_api` | `envoy-gateway` | Envoy Gateway CRDs + controller                    |
| `ingress`     | `nginx`         | rke2-ingress-nginx (bundled)                       |

`host_network: true` binds Traefik directly to the node IP on ports 8000/8443. Set `host_network: false` and `service_type: LoadBalancer` when using MetalLB.

## setup_profiles.yml Example

```yaml
rke2:
  rke21:
    role   : server
    ingress:
      type    : gateway_api
      provider: traefik
      traefik :
        host_network: true
        service_type: ClusterIP
  rke22:
    role       : control
    server_node: rke21
    server_url : "https://rke21.ctlabs.internal:9345"
  rke23:
    role       : control
    server_node: rke21
    server_url : "https://rke21.ctlabs.internal:9345"
  rke24:
    role       : worker
    server_node: rke21
    server_url : "https://rke21.ctlabs.internal:9345"
```

## Tests

```sh
pytest -sv roles/ctlabs_rke2/tests
```
