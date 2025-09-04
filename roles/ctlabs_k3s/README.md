# Ansible Role `ctlabs_k3s`

To setup single-/multi-node k3s cluster.

## Local facts

___Server___

```json
{ 
	"role"  : "server",
	"plane" : "control",
}
```

___Agent (Worker)___

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
