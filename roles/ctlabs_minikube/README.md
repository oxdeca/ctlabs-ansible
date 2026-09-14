# Ansible Role `ctlabs_minikube`

Setup a single-node minikube cluster using the podman driver.

## Ansible Tags

- `minikube` (single-node instance)
- `ctlabs_minikube.precheck` / `package` / `config` / `service` / `charts`

## Prechecks

- OS: debian12
- Virt: kvm

## Helm charts

App charts are data-driven from `ctlabs_minikube.repos` + `ctlabs_minikube.charts`
in the local facts (`ctg_facts.ctlabs_minikube...`, default: empty). Each chart
accepts the same fields as `ctlabs_helm` (`name`, `chart`, `chart_version`,
`namespace`, `kubeconfig`, `create_namespace`, `update_repo_cache`, `wait`,
`atomic`, `skip_crds`, `values`, `values_files`, `resources`), plus `prepull`
(default `true` — the role renders the chart, pulls each image with podman and
`minikube image load`s it into the node before `helm install`, so the node never
depends on direct registry access).

```json
{
  "repos" : [
    { "name": "traefik", "repo_url": "https://traefik.github.io/charts" }
  ],
  "charts": [
    {
      "name"         : "traefik",
      "chart"        : "traefik/traefik",
      "chart_version": "40.0.0",
      "namespace"    : "traefik",
      "wait"         : true
    }
  ]
}
```

`resources` (optional) applies extra objects with `kubernetes.core.k8s` after the
chart is up.

### Running as the minikube user

The cluster runs as the `minikube` system user (systemd unit). Chart tasks
(`helm repo add`, `helm install`/`template`, `podman`, `minikube image load`)
therefore run with `become_user: minikube`: helm resolves the minikube user's
`~/.kube/config` and `~/.config/helm`, and `minikube image load` targets the
profile the unit started. Per-chart `kubeconfig` overrides this. The user needs
podman access (as `minikube start` already requires).

### Prepull on minikube

Minikube nodes pull images **directly** — the kind-style registry TLS failures
don't apply, so the k8s lab profile sets `prepull: false` per chart. The
host-side prepull path (`podman pull` + `minikube image load` as the minikube
user) additionally requires rootless-podman setup for that user (`/etc/subuid`
+ `/etc/subgid` + writable HOME), otherwise it fails with "cannot chdir to
/root" / "potentially insufficient UIDs or GIDs". Keep `prepull: false` unless
the node genuinely can't reach the registry.

### LoadBalancer on minikube (host IP, like k3s/rke2)

MetalLB *assigns* an ExternalIP on minikube but **L2 announcement never answers
ARP from the host** on the docker-in-node/podman bridge (the speaker reconciles
the service but never announces; the VIP is only reachable from inside the node
via kube-proxy IPVS). So the minikube profile does NOT use MetalLB: the traefik
chart stays `service.type: LoadBalancer` and, when a chart carries a
`loadBalancerIP` key, this role patches the svc `status.loadBalancer.ingress`
to that IP (`kubectl patch --subresource=status`) — so `EXTERNAL-IP`, the
ingress ADDRESS and anything reading the svc status show the **host IP**
(`192.168.30.61` here), exactly the observable of the k3s/rke2 svclb. Optional
`loadBalancerSvc` overrides the svc name (default: chart name).

`tasks/proxy.yml` then binds the host: iptables DNAT on the host IP binds
`:80/:443` to the svc **NodePorts** on the node IP (`kubectl get svc`), the same
fallback as `ctlabs_kind.tasks.proxy`. Nothing in the cluster needs to know the
host IP's NIC; the proxy reads `ansible_default_ipv4` and
`podman inspect minikube`.

## Tests

```sh
pytest -sv roles/ctlabs_minikube/tests
```
