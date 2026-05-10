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

### Ingress (nginx-ingress)

```json
{
  "plane"   : "single",
  "ingress" : {
    "type"     : "ingress",
    "provider" : "nginx"
  }
}
```

### Ingress (traefik)

```json
{
  "plane"   : "single",
  "ingress" : {
    "type"     : "ingress",
    "provider" : "traefik"
  }
}
```

### Gateway API (envoy-gateway)

```json
{
  "plane"   : "single",
  "ingress" : {
    "type"     : "gateway_api",
    "provider" : "envoy-gateway"
  }
}
```

### Gateway API (traefik)

```json
{
  "plane"   : "single",
  "ingress" : {
    "type"     : "gateway_api",
    "provider" : "traefik"
  }
}
```
