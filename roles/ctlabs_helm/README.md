# Ansible Role `ctlabs_helm`

Installs the Helm binary, adds Helm repositories, and deploys Helm charts.

## Ansible Tags

| Tag                 | Targets                       |
|---------------------|-------------------------------|
| `helm`              | all helm hosts                |
| `ctlabs_helm`       | all helm hosts                |
| `ctlabs_helm.precheck` | prechecks only            |
| `ctlabs_helm.package`  | helm binary install       |
| `ctlabs_helm.charts`   | repositories + chart installs |

## Prechecks

- OS: centos8, centos9, redhat8, redhat9, debian11, debian12

## Configuration

| Variable                            | Default                                      | Description               |
|-------------------------------------|----------------------------------------------|---------------------------|
| `versions.helm`                     | `4.1.4`                                      | Helm version              |
| `ctlabs_helm.defaults.bin.path`     | `/usr/bin/helm`                              | Binary install path       |
| `ctlabs_helm.defaults.repos`        | `[]`                                         | List of `{name, repo_url}`|
| `ctlabs_helm.defaults.charts`       | `[]`                                         | List of chart deployments |

### Chart fields

| Field            | Required | Description                                             |
|------------------|----------|---------------------------------------------------------|
| `name`           | yes      | Helm release name                                       |
| `chart`          | yes      | Chart reference (repo/chart or OCI URL)                 |
| `namespace`      | yes      | Release namespace                                       |
| `chart_version`  | no       | Chart version to install                                |
| `create_namespace`| no      | Create namespace if missing (default `true`)            |
| `kubeconfig`     | no       | `KUBECONFIG` path to use for the release                |
| `interpreter`    | no       | `ansible_python_interpreter` override (e.g. VRF exec)   |
| `wait`           | no       | Wait for the release to be ready (default `false`)      |
| `atomic`         | no       | Roll back on failure (default `false`)                  |
| `skip_crds`      | no       | Skip CRD handling (default `false`)                     |
| `update_repo_cache` | no    | `helm repo update` before install (default `false`)     |
| `values`         | no       | Inline values dict — rendered to YAML preserving types  |
| `values_files`   | no       | Additional pre-rendered values files to merge           |
| `gateway`        | no       | Dict — enables Gateway API routing for this chart (see below) |

### Gateway API routing

Cluster roles own the infrastructure Gateway (e.g. `traefik-gateway`). When an
app chart needs Gateway API routing, add a `gateway` key to its chart entry;
`ctlabs_helm.tasks.routing` then creates the app-side wiring after the install:
TLS secret, both ReferenceGrants, and the HTTPRoute. Names/versions resolve
against `ctlabs_helm.defaults.gateway` when omitted.

| `gateway` field      | Required | Description                                        |
|----------------------|----------|----------------------------------------------------|
| `name`               | yes      | Gateway object name the route/grants target        |
| `namespace`          | yes      | Namespace the Gateway lives in                     |
| `refgrant_api`       | no       | ReferenceGrant apiVersion (`v1` default; `v1beta1` for k3s bundled Gateway API v1.0.0 CRDs) |
| `tls_secret`         | no       | TLS secret name in the chart namespace             |
| `grant_name`         | no       | Secret-ReferenceGrant name (app namespace)         |
| `attach_grant`       | no       | Attachment-ReferenceGrant name (gateway namespace) |
| `route_name`         | no       | HTTPRoute name                                     |
| `route_backend`      | no       | Backend service name (port 80)                     |
| `route_port`         | no       | Backend service port                               |

Example (k3s, bundled traefik Gateway API v1.0.0 CRDs → `v1beta1` grants):

```yaml
- name        : argocd
  chart       : argo/argo-cd
  namespace   : argo
  kubeconfig  : /etc/rancher/k3s/k3s.yaml
  gateway     :
    name        : traefik-gateway
    namespace   : kube-system
    refgrant_api: v1beta1
```

## Local Facts

Written to `/etc/ansible/facts.d/ctlabs_helm.fact`:

```json
{
  "repos": [
    { "name": "argo", "repo_url": "https://argoproj.github.io/argo-helm" }
  ],
  "charts": [
    {
      "name": "argocd",
      "chart": "argo/argo-cd",
      "namespace": "argo",
      "create_namespace": true,
      "kubeconfig": "/etc/rancher/k3s/k3s.yaml",
      "wait": true,
      "values": {
        "global": { "domain": "argocd.ctlabs.internal" }
      }
    }
  ]
}
```

Per-host resolution via `ctg_facts.ctlabs_helm.{repos,charts}` — fact is authoritative, falls back to role defaults.

## Tests

```sh
pytest -sv roles/ctlabs_helm/tests
```
