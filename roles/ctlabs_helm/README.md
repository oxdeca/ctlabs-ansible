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
