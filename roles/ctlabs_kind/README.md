# Ansible Role `ctlabs_kind`

## Ansible Tags

- `kind`

## Local facts

### Single node cluster (**Default**)

```json
{
  "plane" : "single"
}
```

### Multi node cluster

```json
{
  "plane" : "single",
  "nodes" : 3
}
```

### Ingress (nginx)

```json
{
  "plane"   : "single",
  "ingress" : {
    "enabled" : true,
    "type"    : "nginx"
  }
}
```

### Ingress (traefik)

```json
{
  "plane"   : "single",
  "ingress" : {
    "enabled" : true,
    "type"    : "traefik"
  }
}
```

### Gateway API (envoy-gateway)

```json
{
  "plane"       : "single",
  "gateway_api" : {
    "enabled"  : true,
    "provider" : "envoy-gateway"
  }
}
```

### Gateway API (traefik)

```json
{
  "plane"       : "single",
  "gateway_api" : {
    "enabled"  : true,
    "provider" : "traefik"
  }
}
```

### Helm charts

kind does **not** use `ctlabs_helm` — charts are installed by this role itself,
data-driven from `repos` + `charts` in the local facts (default: empty). Each
chart accepts the same fields as `ctlabs_helm` (`name`, `chart`, `chart_version`,
`namespace`, `kubeconfig`, `create_namespace`, `update_repo_cache`, `wait`,
`atomic`, `skip_crds`, `values`, `resources`), plus `prepull` (default `true` —
kind nodes often cannot reach quay.io, so the role templates the chart, pulls,
saves and `kind load image-archive`s every image before `helm install`).

```json
{
  "plane"   : "single",
  "gateway_api" : { "enabled": true, "provider": "traefik" },
  "repos"   : [
    { "name": "traefik", "repo_url": "https://traefik.github.io/charts" },
    { "name": "argo",    "repo_url": "https://argoproj.github.io/argo-helm" }
  ],
  "charts"  : [
    {
      "name"         : "traefik",
      "chart"        : "traefik/traefik",
      "chart_version": "40.0.0",
      "namespace"    : "traefik",
      "kubeconfig"   : "/root/.kube/config",
      "skip_crds"    : true,
      "wait"         : true
    },
    {
      "name"    : "argocd",
      "chart"   : "argo/argo-cd",
      "namespace": "argo",
      "kubeconfig": "/root/.kube/config"
    }
  ]
}
```

`resources` (optional) applies extra objects with `kubernetes.core.k8s` after the
chart is up — e.g. MetalLB `IPAddressPool`/`L2Advertisement` so `type: LoadBalancer`
services get a real ExternalIP from the kind/podman bridge CIDR.

### LoadBalancer (MetalLB)

kind naturally gives LoadBalancer-services — once an LB controller exists. Add
`metallb` as a chart with a pool in the **kind/podman bridge subnet** (e.g. the
podman `kind` network `10.89.0.0/24` → pool `10.89.0.240-250`):

```json
{
  "plane"       : "single",
  "gateway_api" : { "enabled": true, "provider": "traefik" },
  "repos"       : [
    { "name": "metallb", "repo_url": "https://metallb.github.io/metallb" },
    { "name": "traefik", "repo_url": "https://traefik.github.io/charts" },
    { "name": "argo",    "repo_url": "https://argoproj.github.io/argo-helm" }
  ],
  "charts"      : [
    {
      "name"          : "metallb",
      "chart"         : "metallb/metallb",
      "chart_version" : "0.16.1",
      "namespace"     : "metallb-system",
      "kubeconfig"    : "/root/.kube/config",
      "wait"          : true,
      "values"        : { "frrk8s": { "enabled": false } },
      "resources"     : [
        { "apiVersion" : "metallb.io/v1beta1",
          "kind"       : "IPAddressPool",
          "metadata"   : { "name": "default", "namespace": "metallb-system" },
          "spec"       : { "addresses": ["10.89.0.240-10.89.0.250"] } },
        { "apiVersion" : "metallb.io/v1beta1",
          "kind"       : "L2Advertisement",
          "metadata"   : { "name": "default", "namespace": "metallb-system" },
          "spec"       : { "ipAddressPools": ["default"] } }
      ]
    },
    { "name" : "traefik", "chart" : "traefik/traefik", "version" : "40.0.0", "namespace" : "traefik" },
    { "name" : "argocd",  "chart" : "argo/argo-cd",    "namespace" : "argo" }
  ]
}
```

## Host access (`tasks/proxy.yml`)

The host iptables DNAT forwards `:80`/`:443` to the ingress entry point. The proxy
**prefers the LoadBalancer ExternalIP** when present (`tasks/proxy.yml` reads
`<svc> .status.loadBalancer.ingress[0].ip` and DNATs to it directly) and falls
back to the svc NodePorts on the kind node otherwise. LB mode + `prepull` mean the
VMs' nodes never need direct registry access.

## Objects are templates

Cluster/Gateway-API objects are YAML templates in `templates/`
(`gateway.yml.j2`, `gateway_ns.yml.j2`, `tls_secret.yml.j2`,
`reference_grant.yml.j2`, `attachment_grant.yml.j2`, `httproute.yml.j2`),
rendered with `lookup('template', ...) | from_yaml` into `kubernetes.core.k8s` —
the same convention as `ctlabs_helm`. Chart `resources` stays data-driven in the
profile. Note the TLS secret `slurp`s the CA cert/key **on the target host**
(they live in `/etc/ca-ctlabs/` per host, not on the controller).

## Configuration

| Variable                                            | Default                  | Description                                          |
|-----------------------------------------------------|--------------------------|------------------------------------------------------|
| `versions.kind`                                     | `0.31.0`                 | kind version                                         |
| `versions.k8s`                                      | `1.35.0`                 | Kindest node image k8s version                       |
| `versions.helm`                                     | `4.1.4`                  | Helm binary version (installed by this role)         |
| `ctlabs_kind.defaults.repos`                        | `[]`                     | Helm repositories (`name`, `repo_url`)               |
| `ctlabs_kind.defaults.charts`                       | `[]`                     | Helm charts to deploy (see above)                    |
| `ctlabs_kind.defaults.config.plane`                 | `single`                 | Cluster plane (`single`, `multi`)                    |
| `ctlabs_kind.defaults.config.ingress.enabled`       | `false`                  | Enable ingress controller                            |
| `ctlabs_kind.defaults.config.ingress.type`          | `nginx`                  | Ingress type (`traefik`, `nginx`)                    |
| `ctlabs_kind.defaults.config.gateway_api.enabled`   | `true`                   | Enable Gateway API                                   |
| `ctlabs_kind.defaults.config.gateway_api.provider`  | `traefik`                | Gateway provider (`traefik`, `envoy-gateway`)        |
| `ctlabs_kind.defaults.proxy.interface`              | `enp0s2`                 | Host NIC for the iptables DNAT (`ctg_facts.ctlabs_kind.proxy.interface` overrides) |

> Note: for the Gateway API (traefik) case, the role provisions the Cluster-level
> Gateway API CRDs + the `traefik-gateway` Gateway object (infrastructure), and
> the app wiring (TLS secret, `ReferenceGrant`s, `HTTPRoute`) is applied in
> `tasks/routing.yml` after the argocd chart lands in `tasks/charts.yml`.

## Tests

```sh
pytest -sv roles/ctlabs_kind/tests
```
