# Ansible Role `ctlabs_rke2`

To setup single-/multi-node RKE2 cluster with ArgoCD.

## Ansible Tags

- `ctlabs_rke2` — all tasks
- `ctlabs_rke2.precheck` — OS/virt/var prechecks
- `ctlabs_rke2.package` — rke2 binary, helm, python deps
- `ctlabs_rke2.config` — profile, sysconfig
- `ctlabs_rke2.service` — systemd units, cluster wait, argocd, ingress/gateway

## Local facts

### Server (Default)

```json
{
  "plane" : "control",
  "role"  : "server",
  "ingress" : {
    "type"     : "gateway_api",
    "provider" : "traefik"
  }
}
```

### Server — Ingress (nginx)

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

### Server — Gateway API (envoy-gateway)

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
