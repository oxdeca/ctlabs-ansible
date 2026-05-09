# Ansible Role `ctlabs_k3s`

To setup single-/multi-node k3s cluster.

## Local facts

### Server

```json
{ 
	"role"  : "server",
	"plane" : "control",
}
```

__Ingress__

1. Gateway API (**Default**)

**gatewayclass traefik**
```json
{ 
  "role"  : "server",
  "plane" : "control",
  "ingress" : {
    "type"     : "gateway_api",
    "provider" : "traefik"
  }
}
```

2. Ingress Controller

**nginx-ingress**
```json
{ 
  "role"  : "server",
  "plane" : "control",
  "ingress" : {
    "type"     : "ingress",
    "provider" : "nginx"
  }
}
```

**traefik-ingress**
```json
{ 
  "role"  : "server",
  "plane" : "control",
  "ingress" : {
    "type"     : "ingress",
    "provider" : "traefik"
  }
}
```

### Agent (Worker)

```json
{
    "role"        : "agent",
    "plane"       : "control|data",
    "server_node" : "k3s1",
    "server_url"  : "https://k3s1.ctlabs.internal:6443",
}
```

## Ansible Tags

- k3s (single-node instance)
- k3s-server (server in multi-node cluster)
- k3s-agent  (worker in multi-node cluster; can be in control- or data-plane)
