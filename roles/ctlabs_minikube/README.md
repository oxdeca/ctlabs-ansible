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

## Tests

```sh
pytest -sv roles/ctlabs_minikube/tests
```
