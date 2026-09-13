# Ansible Role `ctlabs_rke2`

Sets up a single- or multi-node RKE2 cluster. Cluster Apps (ArgoCD, Traefik, etc.) are deployed via the separate `ctlabs_helm` role.

## Node Roles

| Role      | Description                                                                    |
|-----------|--------------------------------------------------------------------------------|
| `server`  | Bootstrap node — starts the cluster                                            |
| `control` | Additional control plane node — joins server, runs `rke2 server` via sysconfig |
| `worker`  | Data plane node — joins server, runs `rke2 agent`                              |

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

| Variable                                            | Default                  | Description                                                    |
|-----------------------------------------------------|--------------------------|----------------------------------------------------------------|
| `versions.rke2`                                     | `1.33.3`                 | RKE2 version                                                   |
| `versions.gateway_api`                              | `1.5.0`                  | Gateway API CRDs version                                       |
| `versions.envoy`                                    | `1.0.1`                  | Envoy Gateway version                                          |
| `ctlabs_rke2.defaults.config.ingress.enabled`       | `false`                  | Enable ingress controller                                      |
| `ctlabs_rke2.defaults.config.ingress.type`          | `nginx`                  | Ingress type (`traefik`, `nginx`)                              |
| `ctlabs_rke2.defaults.config.gateway_api.enabled`   | `true`                   | Enable Gateway API                                             |
| `ctlabs_rke2.defaults.config.gateway_api.provider`  | `traefik`                | Gateway provider (`traefik`, `envoy-gateway`)                  |
| `ctlabs_rke2.defaults.config.servicelb.enabled`     | `false`                  | Enable RKE2 ServiceLB (klipper-lb) for `LoadBalancer` services |

> Note: Helm itself, the ArgoCD chart, and the Traefik chart are no longer deployed by this role. They are handled by the separate `ctlabs_helm` role — see its `setup_profiles.yml` `helm:` profile for chart configuration (kubeconfig, values, etc.).

## Local Facts

### Server (bootstrap)

```json
{
  "role"       : "server",
  "server_url" : "https://rke21.ctlabs.internal:9345",
  "ingress"    : {
    "enabled": false,
    "type"   : "nginx"
  },
  "gateway_api": {
    "enabled" : true,
    "provider": "traefik"
  },
  "servicelb": {
    "enabled": true
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

| Section        | Option          | Notes                                                                                                         |
|----------------|-----------------|---------------------------------------------------------------------------------------------------------------|
| `gateway_api`  | `traefik`       | Default — Traefik chart via `ctlabs_helm` role                                                                |
| `gateway_api`  | `envoy-gateway` | Envoy Gateway CRDs + controller                                                                               |
| `ingress`      | `nginx`         | rke2-ingress-nginx (bundled)                                                                                  |
| `ingress`      | `traefik`       | Traefik chart (via `ctlabs_helm`) serving `Ingress` too — this role disables the bundled nginx and only waits |

**Traefik (`ingress.type: traefik`)** uses the same Traefik chart installed by the `ctlabs_helm` role — its `kubernetesIngress` provider is enabled by default, so it serves `Ingress` resources in addition to `Gateway`/`HTTPRoute`. When configured, this role disables the bundled nginx controller (`--disable=rke2-ingress-nginx`) and waits for the Traefik deployment (if already present).

**Traefik (gateway_api mode)** is installed by the `ctlabs_helm` role. Traefik values (hostNetwork, service type, ports, `providers.kubernetesGateway.enabled`) are configured per-host in `setup_profiles.yml` under the `helm:` profile. This role only provisions the supporting resources: Gateway API CRDs and the Traefik `Gateway`. The app wiring (App namespace, TLS secret, `ReferenceGrant`s, `HTTPRoute`) rides with the ArgoCD chart via the `ctlabs_helm` role's `routing.yml` (see the `gateway:` key on the `argocd` chart entry).

> Note: cluster Apps (ArgoCD, Traefik, Gateway routing objects) are deployed via the separate `ctlabs_helm` role.

## setup_profiles.yml Example

```yaml
rke2:
  rke21:
    role       : server
    servicelb:
      enabled : true
    ingress:
      enabled : false
    gateway_api:
      enabled : true
      provider: traefik
  rke22:
    role       : control
    server_node: rke21
    server_url : "https://rke21.ctlabs.internal:9345"
    ingress:
      enabled : false
    gateway_api:
      enabled : false
  rke23:
    role       : control
    server_node: rke21
    server_url : "https://rke21.ctlabs.internal:9345"
    ingress:
      enabled : false
    gateway_api:
      enabled : false
  rke24:
    role       : worker
    server_node: rke21
    server_url : "https://rke21.ctlabs.internal:9345"
    ingress:
      enabled : false
    gateway_api:
      enabled : false
```

## ServiceLB (LoadBalancer services)

When `servicelb.enabled` is `true`, the server starts with `--enable-servicelb` and RKE2's built-in ServiceLB (klipper-lb) assigns an external IP to every `type: LoadBalancer` service. Verified on rke21: enabling ServiceLB gave the `traefik` cluster's `LoadBalancer` service an EXTERNAL-IP, which Traefik copies to the Gateway `status.address`.

### Is the controller running?

```sh
kubectl logs -n kube-system cloud-controller-manager-rke21.ctlabs.internal | grep service-lb
# -> Started "service-lb-controller"   (running)
# -> "service-lb-controller" is disabled   (off — add servicelb.enabled: true + re-run)
```

### The klipper-lb pod

For every `LoadBalancer` service rke2 spawns one daemonset + one pod (`svclb-<svc>-<hash>` / `rancher/klipper-lb:vX`) that forwards node ports to the pods:

```sh
kubectl get ds -n kube-system -o wide | grep svclb
kubectl get pods -n kube-system -o wide | grep svclb
```

### The LoadBalancer service details

```sh
kubectl get svc -n traefik traefik -o wide        # EXTERNAL-IP column
kubectl describe svc -n traefik traefik           # events / load balancer status
kubectl -n traefik get svc traefik -o jsonpath='{.status.loadBalancer.ingress}'
```

### Diagnosing `<pending>` EXTERNAL-IP

```sh
kubectl describe svc traefik -n traefik           # Events section
kubectl logs -n kube-system cloud-controller-manager-rke21.ctlabs.internal | grep -iE "lb|svclb|error"
```

Common causes: ServiceLB disabled (see above), or the ServiceLB feature flag missing from the server unit.

> On a multi-IP node klipper-lb picks one node IP; if that is not client-reachable, pin it via `spec.loadBalancerIP`/annotations on the Service.

## Tests

```sh
pytest -sv roles/ctlabs_rke2/tests
```
