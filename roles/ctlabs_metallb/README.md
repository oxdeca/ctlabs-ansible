# Ansible Role `ctlabs_metallb`

## Ansible Tags

- `ctlabs_metallb`
- `ctlabs_metallb.precheck`
- `ctlabs_metallb.package`
- `ctlabs_metallb.config`

## Prechecks

- OS: debian12, centos9, redhat9

## Description

Installs MetalLB (bare-metal LoadBalancer) via Helm and configures an IPAddressPool with L2Advertisement. Intended for use with RKE2, k3s, or kind clusters that lack a cloud LoadBalancer controller.

## Configuration

| Variable                                         | Default                          | Description                      |
|--------------------------------------------------|----------------------------------|----------------------------------|
| `ctlabs_metallb.defaults.helm.version`           | `0.14.9`                         | MetalLB Helm chart version       |
| `ctlabs_metallb.defaults.helm.ns`                | `metallb-system`                 | Release namespace                |
| `ctlabs_metallb.defaults.pool.name`              | `default`                        | IPAddressPool name               |
| `ctlabs_metallb.defaults.pool.addresses`         | `[192.168.30.240-250]`           | IP range(s) for LoadBalancer     |
| `ctlabs_metallb.defaults.kubeconfig`             | `/etc/rancher/rke2/rke2.yaml`    | Kubeconfig path                  |

## Tests

```sh
pytest -sv roles/ctlabs_metallb/tests
```
