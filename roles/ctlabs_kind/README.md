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

## Configuration

| Variable                                            | Default                  | Description                                          |
|-----------------------------------------------------|--------------------------|------------------------------------------------------|
| `versions.kind`                                     | `0.31.0`                 | kind version                                         |
| `versions.k8s`                                      | `1.35.0`                 | Kindest node image k8s version                       |
| `ctlabs_kind.defaults.config.plane`                 | `single`                 | Cluster plane (`single`, `multi`)                    |
| `ctlabs_kind.defaults.config.ingress.enabled`       | `false`                  | Enable ingress controller                            |
| `ctlabs_kind.defaults.config.ingress.type`          | `nginx`                  | Ingress type (`traefik`, `nginx`)                    |
| `ctlabs_kind.defaults.config.gateway_api.enabled`   | `true`                   | Enable Gateway API                                   |
| `ctlabs_kind.defaults.config.gateway_api.provider`  | `traefik`                | Gateway provider (`traefik`, `envoy-gateway`)        |

> Note: for the Gateway API (traefik) case, the role provisions the provider
> (Traefik chart + Gateway API CRDs) and the ArgoCD app wiring (TLS secret,
> `ReferenceGrant`s, `HTTPRoute`) directly, since it deploys ArgoCD itself.

## Tests

```sh
pytest -sv roles/ctlabs_kind/tests
```
