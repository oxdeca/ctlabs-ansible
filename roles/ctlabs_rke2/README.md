# Ansible Role `ctlabs_rke2`

Sets up a single- or multi-node RKE2 cluster. Cluster Apps (ArgoCD, Traefik, etc.) are deployed via the separate `ctlabs_helm` role.

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
| `versions.gateway_api`                              | `1.5.0`                  | Gateway API CRDs version                            |
| `versions.envoy`                                    | `1.0.1`                  | Envoy Gateway version                               |
| `ctlabs_rke2.defaults.config.ingress.type`          | `gateway_api`            | Ingress type (`ingress`, `gateway_api`)             |
| `ctlabs_rke2.defaults.config.ingress.provider`      | `traefik`                | Provider (`traefik`, `nginx`, `envoy-gateway`)      |

> Note: Helm itself, the ArgoCD chart, and the Traefik chart are no longer deployed by this role. They are handled by the separate `ctlabs_helm` role — see its `setup_profiles.yml` `helm:` profile for chart configuration (kubeconfig, values, etc.).

## Local Facts

### Server (bootstrap)

```json
{
  "role"      : "server",
  "server_url": "https://rke21.ctlabs.internal:9345",
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
| `gateway_api` | `traefik`       | Default — Traefik chart via `ctlabs_helm` role     |
| `gateway_api` | `envoy-gateway` | Envoy Gateway CRDs + controller                    |
| `ingress`     | `nginx`         | rke2-ingress-nginx (bundled)                       |

**Traefik (gateway_api mode)** is installed by the `ctlabs_helm` role. Traefik values (hostNetwork, service type, ports, `providers.kubernetesGateway.enabled`) are configured per-host in `setup_profiles.yml` under the `helm:` profile. This role only provisions the supporting resources (Gateway API CRDs, Traefik `GatewayClass`/`Gateway`, ArgoCD `HTTPRoute`).

## setup_profiles.yml Example

```yaml
rke2:
  rke21:
    role   : server
    ingress:
      type    : gateway_api
      provider: traefik
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
