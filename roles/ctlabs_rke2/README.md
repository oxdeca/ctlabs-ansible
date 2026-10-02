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
| `ctlabs_rke2.defaults.config.coredns.resources`     | `100m`/`128Mi` req+limit | CPU/memory for the bundled `rke2-coredns` chart, applied via a `HelmChartConfig` |
| `ctlabs_rke2.defaults.config.coredns.split_dns.enabled` | `true`               | Dedicated CoreDNS forward zone for the lab domain, bypassing the public resolver fallback (see "CoreDNS" below) |
| `ctlabs_rke2.defaults.config.coredns.public_resolvers`  | `8.8.8.8`, `8.8.4.4`, `1.1.1.1`, `1.0.0.1` | Nameservers excluded when auto-deriving the internal forward list from `/etc/resolv.conf` |

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
  },
  "coredns": {
    "resources": {
      "requests": { "cpu": "100m", "memory": "128Mi" },
      "limits"  : { "cpu": "250m", "memory": "128Mi" }
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

## CoreDNS

Two independent, additive overrides live under `ctg_facts.ctlabs_rke2.coredns.*`.
Both are applied **once, cluster-wide**, server node only, via a single
`HelmChartConfig/rke2-coredns` in `kube-system` (RKE2's native per-chart values
override — its own helm-controller re-merges it into the bundled chart release;
not per-node, not a pod restart you trigger yourself).

### Resources (CPU throttling)

The bundled `rke2-coredns` chart defaults to `cpu: 100m` request+limit, single
replica (the autoscaler only adds replicas per `coresPerReplica`/`nodesPerReplica`
— see its `rke2-coredns-rke2-coredns-autoscaler` ConfigMap). On a busy single-node
lab that 100m limit can get CPU-throttled (`cat /sys/fs/cgroup/.../cpu.stat` →
non-zero `nr_throttled`) — a real, measured, but usually **secondary** contributor
to intermittent DNS failures; see "Split DNS" below for the primary cause.

Override via `ctg_facts.ctlabs_rke2.coredns.resources`:

```json
{
  "coredns": {
    "resources": {
      "requests": { "cpu": "100m", "memory": "128Mi" },
      "limits"  : { "cpu": "250m", "memory": "128Mi" }
    }
  }
}
```

### Split DNS (the actual root cause of "dial tcp: lookup ... no such host")

**Root cause (confirmed 2026-10-01, not just theorized)**: every ctlabs node's
`/etc/resolv.conf` lists the lab's real internal nameservers *and* a public
fallback (`8.8.8.8`), e.g.:

```
domain ctlabs.internal
nameserver 192.168.10.11
nameserver 192.168.20.11
nameserver 8.8.8.8
```

CoreDNS's `forward` plugin defaults to policy `random` across **every** IP in
that list. A query for an internal name (e.g. `vdb1.ctlabs.internal`) that
happens to land on `8.8.8.8` gets back a clean NXDOMAIN (Google has no idea
about `.internal`) — not a timeout, a *valid* authoritative-looking negative
answer, so CoreDNS doesn't retry another upstream. The `cache 30` plugin then
caches that NXDOMAIN for 30s and serves it to every client that asks in that
window. Net effect: DNS for internal names fails in solid ~30s blocks (1-in-3
chance per cache window), then recovers, with nothing else having changed —
exactly the "stale ArgoCD cache" look this was originally misdiagnosed as.

**Fix**: a dedicated CoreDNS server block for the lab's own domain that forwards
*only* to the real internal nameservers, never touching `8.8.8.8` for anything
under that domain; the catch-all `.:53` block is untouched and still uses all of
`/etc/resolv.conf` (including the public fallback) for genuine external lookups
(pulling images, etc.). **Self-adapting, not hardcoded**: the role reads the
rke2 server node's own `/etc/resolv.conf` at apply time, takes the `domain`/
`search` line as the zone, and takes every `nameserver` IP *except* a configurable
public-resolver blocklist (`ctlabs_rke2.defaults.config.coredns.public_resolvers`
— default `8.8.8.8`, `8.8.4.4`, `1.1.1.1`, `1.0.0.1`). If no domain or no
non-public nameserver is found, no override is emitted and the chart's stock
Corefile is left exactly as-is — safe to leave on by default.

Controlled by `ctg_facts.ctlabs_rke2.coredns.split_dns.enabled` (default `true`
— this is a correctness fix, not a tuning knob). Manual override of the parsed
values, if ever needed:

```json
{
  "coredns": {
    "split_dns": {
      "enabled": true,
      "domain": "ctlabs.internal",
      "nameservers": ["192.168.10.11", "192.168.20.11"]
    }
  }
}
```

**Verified live on rke201** (2026-10-01): 0/30 failures hammering
`getent hosts vdb1.ctlabs.internal` from inside a cluster pod immediately after
applying, external lookups (`github.com`) still resolve fine through the
catch-all block.

The actual mechanism RKE2's bundled chart uses is a structured `servers:` list
(upstream `coredns/helm` chart schema — `zones`/`port`/`plugins[].name`+
`parameters`+`configBlock`), **not** a raw `corefile.override` string key (that
key is silently ignored by this chart version — confirmed by testing it directly
against the live ConfigMap and seeing zero effect, don't reach for it from
generic CoreDNS-on-Kubernetes advice).
```

Applied as `kubectl get helmchartconfig rke2-coredns -n kube-system` — RKE2's
helm-controller re-merges it into the `rke2-coredns` HelmChart release. Defaults
match upstream exactly (no-op) so existing labs are unaffected until a fact
overrides them.

## `crictl` config symlink

Every rke2 node (server/control/worker) gets `/etc/crictl.yaml` symlinked to
`/var/lib/rancher/rke2/agent/etc/crictl.yaml` (the containerd socket rke2 actually
uses, `unix:///run/k3s/containerd/containerd.sock` — not the autodetected default
`crictl` falls back to) so `crictl ps`/`crictl stats`/etc. work out of the box
without `--config`/`--runtime-endpoint` flags or a `CONTAINER_RUNTIME_ENDPOINT`
env var. Applied once the node's own rke2 service is up (that file is generated by
the agent at runtime, not present at install time).

## Tests

```sh
pytest -sv roles/ctlabs_rke2/tests
```
