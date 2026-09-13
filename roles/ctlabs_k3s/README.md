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
  "role"       : "server",
  "server_url" : "https://k3s1.ctlabs.internal:6443",
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

## Controller Options

Ingress and Gateway API are independent, co-installable sections.

| Section       | Key        | Options       | Notes                                  |
|---------------|------------|---------------|----------------------------------------|
| `ingress`     | `enabled`  | `true/false`  | Run an ingress controller              |
| `ingress`     | `type`     | `nginx`       | nginx-ingress via manifest             |
| `gateway_api` | `enabled`  | `true/false`  | Program the Gateway API               |
| `gateway_api` | `provider` | `traefik`     | Default — uses k3s bundled Traefik     |
| `gateway_api` | `provider` | `envoy-gateway` | Envoy Gateway CRDs + controller     |
| `servicelb`   | `enabled`  | `true/false`  | k3s bundled klipper-lb (`true` default; `false` ⇒ `--disable=servicelb`) |

Full facts example (Traefik as Gateway API provider, no ingress, ServiceLB on):

```json
{
  "role"       : "server",
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

## ServiceLB (LoadBalancer services)

k3s bundles its own ServiceLB (klipper-lb), enabled by default. Setting `servicelb.enabled: false` adds `--disable=servicelb` to the server unit, disabling it.

For every `LoadBalancer` service k3s spawns one daemonset + one pod (`svclb-<svc>-<hash>` / `rancher/klipper-lb:vX`) that forwards node ports to the pods. The node IP becomes the service's external IP, which Traefik also copies to the Gateway `status.address`.

```sh
kubectl get ds -n kube-system -o wide | grep svclb
kubectl get pods -n kube-system -o wide | grep svclb
kubectl get svc -n traefik traefik -o wide              # EXTERNAL-IP column
kubectl describe svc -n traefik traefik                 # events / load balancer status
kubectl -n traefik get svc traefik -o jsonpath='{.status.loadBalancer.ingress}'
```

Diagnosing a `<pending>` EXTERNAL-IP:

```sh
kubectl describe svc -n traefik traefik              # events
journalctl -u k3s-server | grep -iE "servicelb|svclb" # k3s server process (runs the controller in-process)
```

Common causes: ServiceLB disabled via `--disable=servicelb`, or the flag missing from the `k3s-server.service` unit on the node. Unlike rke2, k3s runs the ServiceLB controller inside the `k3s-server` process itself (no `cloud-controller-manager` pod to check).

## setup_profiles.yml Example

```yaml
k3s:
  k3s1:
    role: server
    ingress:
      enabled: false
    gateway_api:
      enabled : true
      provider: traefik
    servicelb:
      enabled: true
  k3s2:
    role       : control
    server_node: k3s1
    server_url : "https://k3s1.ctlabs.internal:6443"
    ingress   :
      enabled: false
    gateway_api:
      enabled: false
  k3s3:
    role       : control
    server_node: k3s1
    server_url : "https://k3s1.ctlabs.internal:6443"
    ingress   :
      enabled: false
    gateway_api:
      enabled: false
  k3s4:
    role       : worker
    server_node: k3s1
    server_url : "https://k3s1.ctlabs.internal:6443"
    ingress   :
      enabled: false
    gateway_api:
      enabled: false
```

## Tests

```sh
pytest -sv roles/ctlabs_k3s/tests
```
