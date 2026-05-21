# Ansible Role `ctlabs_rke2`

To setup single-/multi-node RKE2 cluster with ArgoCD.

## Ansible Tags

- `ctlabs_rke2` — all tasks
- `ctlabs_rke2.precheck` — OS/virt/var prechecks
- `ctlabs_rke2.package` — rke2 binary, helm, python deps
- `ctlabs_rke2.config` — profile, sysconfig
- `ctlabs_rke2.service` — systemd units, cluster wait, argocd, ingress/gateway

## Prechecks

- OS: debian11, debian12, centos8, centos9, redhat9
- Virt: kvm

## Configuration

| Variable                                         | Default                          | Description                        |
|--------------------------------------------------|----------------------------------|------------------------------------|
| `versions.rke2`                                  | `1.33.3`                         | RKE2 version                       |
| `versions.helm`                                  | `3.16.1`                         | Helm version                       |
| `versions.traefik`                               | `40.0.0`                         | Traefik Helm chart version         |
| `versions.gateway_api`                           | `1.5.0`                          | Gateway API CRDs version           |
| `versions.envoy`                                 | `1.0.1`                          | Envoy Gateway version              |
| `ctlabs_rke2.defaults.ingress.traefik.host_network` | `false`                      | Bind Traefik directly to node IP   |
| `ctlabs_rke2.defaults.ingress.traefik.service_type` | `ClusterIP`                  | Traefik service type               |
| `ctlabs_rke2.defaults.argocd.host`              | `argocd.ctlabs.internal`         | ArgoCD hostname                    |
| `ctlabs_rke2.defaults.config.ingress.type`       | `gateway_api`                    | Ingress type (`ingress`, `gateway_api`) |
| `ctlabs_rke2.defaults.config.ingress.provider`   | `traefik`                        | Ingress provider (`traefik`, `nginx`, `envoy-gateway`) |

## Local facts

### Traefik Gateway API — hostNetwork mode (default for bare-metal)

```json
{
  "plane" : "control",
  "role"  : "server",
  "ingress" : {
    "type"     : "gateway_api",
    "provider" : "traefik",
    "traefik"  : {
      "host_network" : true,
      "service_type" : "ClusterIP"
    }
  }
}
```

Traefik binds directly to node IP on ports 8000/8443. Requires MetalLB for LoadBalancer IP if `host_network: false`.

### Traefik Gateway API — LoadBalancer mode (with MetalLB)

```json
{
  "plane" : "control",
  "role"  : "server",
  "ingress" : {
    "type"     : "gateway_api",
    "provider" : "traefik",
    "traefik"  : {
      "host_network" : false,
      "service_type" : "LoadBalancer"
    }
  }
}
```

Requires the `ctlabs_metallb` role to be deployed on the same host.

### Ingress (nginx)

```json
{
  "plane" : "control",
  "role"  : "server",
  "ingress" : {
    "type"     : "ingress",
    "provider" : "nginx"
  }
}
```

Disables rke2-ingress-nginx for non-nginx providers. Envoy Gateway and Traefik require `gateway_api` type.

### Gateway API (envoy-gateway)

```json
{
  "plane" : "control",
  "role"  : "server",
  "ingress" : {
    "type"     : "gateway_api",
    "provider" : "envoy-gateway"
  }
}
```

### Agent (Worker)

```json
{
  "role"        : "agent",
  "plane"       : "control|data",
  "server_node" : "rke2-1",
  "server_url"  : "https://rke2-1.ctlabs.internal:9345"
}
```

## Tests

```sh
pytest -sv roles/ctlabs_rke2/tests
```
