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
chart is up — e.g. MetalLB `IPAddressPool`/`L2Advertisement` for `type: LoadBalancer`
services (a standard kind networking option; otherwise the role's host iptables
DNAT targets the ingress service NodePorts).

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

> Note: for the Gateway API (traefik) case, the role provisions the Cluster-level
> Gateway API CRDs + the `traefik-gateway` Gateway object (infrastructure), and
> the app wiring (TLS secret, `ReferenceGrant`s, `HTTPRoute`) is applied in
> `tasks/routing.yml` after the argocd chart lands in `tasks/charts.yml`.

## Tests

```sh
pytest -sv roles/ctlabs_kind/tests
```
