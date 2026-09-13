# Ansible Role `ctlabs_k8s`

Sets up a single- or multi-node Kubernetes cluster with `kubeadm`, including CNI (calico/flannel/weave), optional ingress-nginx, metrics-server, kube-vip, and longhorn.

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
