# Ansible Role `ctlabs_minikube`

Setup a single-node minikube cluster using the podman driver.

## Ansible Tags

- `minikube` (single-node instance)

## Prechecks

- OS: debian12
- Virt: kvm

## Tests

```sh
pytest -sv roles/ctlabs_minikube/tests
```
