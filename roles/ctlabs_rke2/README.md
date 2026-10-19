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
| `ctlabs_rke2.defaults.config.cni`                   | `canal`                  | Container Network Interface (`canal`, `cilium`, `multus`, `none`). Written to `/etc/rancher/rke2/config.yaml` as `cni: <value>` when not the RKE2 default. `cilium` deploys RKE2's bundled Cilium chart |
| `ctlabs_rke2.defaults.config.cilium.kube_proxy_replacement` | `true`          | Cilium only: disable kube-proxy (`disable-kube-proxy: true` in config.yaml) and set `kubeProxyReplacement: true` on the `rke2-cilium` chart via a `HelmChartConfig` |
| `ctlabs_rke2.defaults.config.cilium.operator_replicas` | `1`                    | Cilium only: `operator.replicas` on the `rke2-cilium` chart |
| `ctlabs_rke2.defaults.config.cilium.k8s_service_host` | `127.0.0.1`           | Cilium only (kube-proxy replacement): `k8sServiceHost` on the `rke2-cilium` chart — the apiserver address Cilium bootstraps against before its eBPF datapath is up |
| `ctlabs_rke2.defaults.config.cilium.k8s_service_port` | `6443`               | Cilium only: `k8sServicePort` (pairs with `k8sServiceHost`) |
| `ctlabs_rke2.defaults.config.cilium.lb.ip_pool.name` | `ctlabs`               | Cilium only: name of the `CiliumLoadBalancerIPPool` for native `LoadBalancer` VIPs |
| `ctlabs_rke2.defaults.config.cilium.lb.ip_pool.cidrs` | `[]`                  | Cilium only: CIDRs the pool may allocate (e.g. `["192.168.30.100/32"]`). Non-empty **activates** Cilium's native LB (see below); empty = no-op |
| `ctlabs_rke2.defaults.config.cilium.lb.l2.interfaces` | `[]`                 | Cilium only: interfaces (regex, e.g. `["enp0s2"]`) the `CiliumL2AnnouncementPolicy` ARP-announces VIPs on; empty = auto |
| `ctlabs_rke2.defaults.config.ingress.enabled`       | `false`                  | Enable ingress controller                                      |
| `ctlabs_rke2.defaults.config.ingress.type`          | `nginx`                  | Ingress type (`traefik`, `nginx`)                              |
| `ctlabs_rke2.defaults.config.gateway_api.enabled`   | `true`                   | Enable Gateway API                                             |
| `ctlabs_rke2.defaults.config.gateway_api.provider`  | `traefik`                | Gateway provider (`traefik`, `envoy-gateway`, `cilium`) — `cilium` enables Cilium's embedded Gateway API implementation |
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
  "cni"        : "cilium",
  "cilium"     : {
    "kube_proxy_replacement" : true,
    "operator_replicas"      : 1
  },
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

**Traefik (`ingress.type: traefik`)** uses the same Traefik chart installed by the `ctlabs_helm` role — its `kubernetesIngress` provider is enabled by default, so it serves `Ingress` resources in addition to `Gateway`/`HTTPRoute`. When configured, this role disables the bundled nginx controller (`disable: [rke2-ingress-nginx]` in config.yaml) and waits for the Traefik deployment (if already present).

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

## CNI / Cilium

RKE2 ships its CNI as a bundled chart, so replacing it is a single opt-in:
set `cni` in the `setup_profiles.yml` `rke2:` profile for the **server** node
(and each `control` node) and the role writes it to that node's
`/etc/rancher/rke2/config.yaml`. `canal` is the RKE2 default and emits no key,
so labs that don't set `cni` are byte-for-byte unchanged.

```yaml
rke2:
  rke21:
    role: server
    cni : cilium
  rke22:
    role: control
    server_node: rke21
    cni : cilium
```

`cilium` deploys RKE2's packaged `rke2-cilium` chart (no external manifests, no
internet dependency beyond the RKE2 bundle). The value is validated against
`ctlabs_rke2.defaults.config.cni_supported` (`canal`, `cilium`, `multus`,
`none`); an unknown value fails the precheck.

### kube-proxy replacement

With `cni: cilium`, kube-proxy is **disabled by default** — Cilium replaces it
(eBPF service handling). This is applied through two coordinated mechanisms,
both required:

1. `disable-kube-proxy: true` in `/etc/rancher/rke2/config.yaml` (server +
   control nodes) — stops RKE2 from deploying the kube-proxy static pods.
2. A `HelmChartConfig/rke2-cilium` in `kube-system`, dropped into
   `/var/lib/rancher/rke2/server/manifests/` **before** the server starts, with
   `kubeProxyReplacement: true` (and `operator.replicas: 1` for single-node
   labs) — RKE2's deploy controller merges it into the bundled chart release.

Setting only one of the two leaves services still flowing through kube-proxy.
Override per-host via the `cilium:` fact block if a lab ever needs kube-proxy
back:

```json
{ "cni": "cilium", "cilium": { "kube_proxy_replacement": false } }
```

#### The `k8sServiceHost` bootstrap (do not remove)

When `kubeProxyReplacement` is on, the chart **must** also carry
`k8sServiceHost` / `k8sServicePort` pointing at the local apiserver:

```yaml
kubeProxyReplacement: true
k8sServiceHost: "127.0.0.1"
k8sServicePort: "6443"
```

Without it Cilium tries to reach the apiserver at the **ClusterIP**
(`10.43.0.1:443`), which only exists *because* Cilium/kube-proxy program
service NAT — a chicken-and-egg deadlock. In steady state the leftover kube-proxy
iptables rules can mask it, but after a **reboot** (or `iptables` flush) the
cilium agent crash-loops in `Init:CrashLoopBackOff` with:

```
Unable to contact k8s api-server ... Get "https://10.43.0.1:443/...": dial tcp 10.43.0.1:443: i/o timeout
```

`127.0.0.1:6443` is correct cluster-wide: control-plane nodes answer with the
local `kube-apiserver`, worker nodes with RKE2's own `rke2` process which proxies
to the server (see upstream Cilium "Installation using Rancher" / RKE2 "Kube-proxy
replacement" docs). Override per-host only if a lab uses a load-balanced API
endpoint:

```json
{ "cni": "cilium", "cilium": { "k8s_service_host": "192.168.30.41" } }
```

### Gateway API provider `cilium`

`gateway_api.provider` accepts a third value, `cilium`, which enables Cilium's
embedded Gateway API implementation on the chart (`gatewayAPI.enabled: true` in
the same `HelmChartConfig`) — for labs that want Cilium as the gateway without
traefik/envoy-gateway. The default `traefik` provider never emits the
`gatewayAPI` key, so cilium's Gateway API controller stays off and traefik
keeps serving `Gateway`/`HTTPRoute` as before. Note the Gateway API CRDs are
still applied by this role after cluster start (same as for the other
providers); the cilium gateway controller tolerates the brief absence and
picks them up once applied.

### Native LoadBalancer (required with kube-proxy replacement)

> **rke2 ServiceLB does not work under Cilium kube-proxy replacement.**
> `svclb-*` (klipper-lb) DNATs LB traffic to the Service **ClusterIP** and relies
> on kube-proxy's iptables to resolve it; Cilium's eBPF does not translate that
> forwarded packet, so the `LoadBalancer` EXTERNAL-IP is black-holed (ClusterIP
> and NodePort keep working). Leftover kube-proxy iptables rules mask this until
> the next reboot — exactly like the `k8sServiceHost` deadlock above. Use
> Cilium's native LB instead.

Set a VIP pool on the **server** node's `cilium.lb` fact; the role then enables
Cilium L2 announcements on the chart, writes a `CiliumLoadBalancerIPPool` +
`CiliumL2AnnouncementPolicy` after the cluster is up, and suppresses rke2's
servicelb:

```yaml
rke2:
  rke21:
    role: server
    cni : cilium
    cilium:
      kube_proxy_replacement: true
      lb:
        ip_pool:
          # /32 entries hand out fixed VIPs; a CIDR is a range.
          # The node's OWN data-plane IP is a valid VIP (Cilium assigns it
          # with no conflict) — this keeps the lab's "everything talks to the
          # host IP" model with no extra address to track.
          cidrs: ["192.168.30.41/32"]
        l2:
          # must sit on the client-reachable (data-plane) segment
          interfaces: ["enp0s2"]
```

Cilium's built-in LB IPAM assigns the VIP to every `LoadBalancer` service
(no `loadBalancerClass` needed once rke2 servicelb is off) and L2 announcements
ARP it from the given interface. `servicelb.enabled` is ignored (and not
written to config.yaml) while this is active — the two cannot coexist.

Using the **node's own data-plane IP** as the `/32` VIP is supported (verified:
Cilium allocates it, no `CiliumLoadBalancerIPPool` conflict, LB frontends get
active backends). It's the right pick when the lab addresses services by the
host IP, and needs no separate address. The trade-off is the usual one for a
node-bound VIP: it is served by that node only (no L2 failover) — fine for the
single-server labs.

```sh
kubectl get ciliumloadbalancerippools.cilium.io
kubectl get ciliuml2announcementpolicies.cilium.io
kubectl get svc -A | grep LoadBalancer     # EXTERNAL-IP comes from the pool
```

> The `interfaces` regex must match the NIC on the network clients can reach;
> with a separate management/data split (e.g. `enp0s1` mgmt / `enp0s2` data)
> the VIP is only reachable from the data segment.

## ServiceLB (LoadBalancer services)

> **Incompatible with Cilium kube-proxy replacement** — see "Native
> LoadBalancer" above. Keep ServiceLB only on `canal` labs (or cilium labs that
> left `kube_proxy_replacement: false`).

When `servicelb.enabled` is `true`, the server starts with `enable-servicelb: true` (config.yaml) and RKE2's built-in ServiceLB (klipper-lb) assigns an external IP to every `type: LoadBalancer` service. Verified on rke21: enabling ServiceLB gave the `traefik` cluster's `LoadBalancer` service an EXTERNAL-IP, which Traefik copies to the Gateway `status.address`.

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
