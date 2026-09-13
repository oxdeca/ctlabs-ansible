# Ansible Role `ctlabs_k8s`

Sets up a single- or multi-node Kubernetes cluster with `kubeadm`, including CNI (calico/flannel/weave), metrics-server, and kube-vip. The Kubernetes version is pinned in `versions.k8s` (default `1.36.4`).

> Components that used to be deployed via raw manifests (longhorn, ingress/traefik) now come from Helm charts owned by [`ctlabs_helm`](../ctlabs_helm/README.md) — see the cluster's `helm` profile in `setup_profiles.yml`.

## Ansible Tags

- `ctlabs_k8s`
- `ctlabs_k8s.precheck`
- `ctlabs_k8s.package`
- `ctlabs_k8s.config`
- `ctlabs_k8s.service`

## Prechecks

- OS: rhel8, centos8, centos9, debian12
- Virt: kvm

## Configuration

| Variable                                  | Default     | Description                                     |
|-------------------------------------------|-------------|-------------------------------------------------|
| `ctlabs_k8s_master_ip`                    | node IP     | Control plane advertise address                 |
| `ctlabs_k8s_pod_cidr`                     | `10.8.15.0/24` | Pod network subnet (must match CNI config)  |
| `ctlabs_k8s_prometheus`                   | `false`     | Deploy kube-prometheus                         |
| `ctlabs_k8s.defaults.config.network`      | `calico`    | CNI (`calico`, `flannel`, `weave`)             |
| `ctlabs_k8s.defaults.config.kube_vip`     | `false`     | Enable kube-vip for HA control plane           |
| `ctlabs_k8s.defaults.config.schedule_master` | `false`  | Taint-free control plane (schedule workloads)  |

## Tests

```sh
pytest -sv roles/ctlabs_k8s/tests
```
