# Ansible Role `ctlabs_argocd_apps`

Declares ArgoCD `Application` objects — cert-manager, external-secrets, and
anything else you want reconciled by ArgoCD instead of by `helm`.

**This role does not install ArgoCD.** The `argo/argo-cd` chart is installed by
`ctlabs_helm`; this role only creates the `Application` CRs that ArgoCD then
manages. Play order matters: `ctlabs_helm` must run first.

With no applications declared the role is a complete no-op, so it is safe to
list on every cluster lab.

## Ansible Tags

| Tag                               | Targets                          |
|-----------------------------------|----------------------------------|
| `ctlabs_argocd_apps`              | all role tasks                   |
| `ctlabs_argocd_apps.precheck`     | prechecks only                   |
| `ctlabs_argocd_apps.applications` | CRD wait + apply + health wait   |
| `ctlabs_argocd_apps.facts`        | local facts write (setup play)   |

## Prechecks

- OS: centos8, centos9, redhat8, redhat9, debian11, debian12
- Each application has `name` and a `source` mapping containing at least `repoURL`
- **No application name may collide with a `ctlabs_helm` chart name** — Helm and
  ArgoCD must never manage the same release, or they revert each other forever
  and the app sits permanently `OutOfSync` with no obvious cause. The precheck
  reads `ctg_facts.ctlabs_helm.charts` and fails loudly on a conflict.

## Configuration

| Variable                                     | Default                                             | Description                                                                                  |
|----------------------------------------------|-----------------------------------------------------|----------------------------------------------------------------------------------------------|
| `ctlabs_argocd_apps.defaults.namespace`      | `argocd`                                            | ArgoCD control-plane namespace (Application CRs go here; the ctlabs labs use `argo`)         |
| `ctlabs_argocd_apps.defaults.kubeconfig`     | `""`                                                | `KUBECONFIG` path; empty = controller default                                                |
| `ctlabs_argocd_apps.defaults.interpreter`    | `""`                                                | `ansible_python_interpreter` override, e.g. `/usr/sbin/ip vrf exec default /usr/bin/python3` |
| `ctlabs_argocd_apps.defaults.project`        | `default`                                           | default ArgoCD AppProject                                                                    |
| `ctlabs_argocd_apps.defaults.server`         | `https://kubernetes.default.svc`                    | default destination API server                                                               |
| `ctlabs_argocd_apps.defaults.sync_policy`    | automated (prune, selfHeal, `CreateNamespace=true`) | default `spec.syncPolicy`                                                                    |
| `ctlabs_argocd_apps.defaults.finalizers`     | `[resources-finalizer.argocd.argoproj.io]`          | cascade-delete resources on Application removal; `[]` keeps them                             |
| `ctlabs_argocd_apps.defaults.wait`           | `true`                                              | wait for `Synced` + `Healthy` after apply                                                    |
| `ctlabs_argocd_apps.defaults.wait_timeout`   | `600`                                               | per-application wait budget (seconds)                                                        |
| `ctlabs_argocd_apps.defaults.wait_delay`     | `10`                                                | poll interval while waiting                                                                  |
| `ctlabs_argocd_apps.defaults.crd_wait`       | `300`                                               | wait for the `applications.argoproj.io` CRD                                                  |
| `ctlabs_argocd_apps.defaults.applications`   | `[]`                                                | applications to declare (normally supplied per host as a local fact)                         |

### Application fields

| Field          | Required | Description                                                  |
|----------------|----------|--------------------------------------------------------------|
| `name`         | yes      | Application name                                             |
| `source`       | yes      | ArgoCD `spec.source`, passed through **verbatim** (below)    |
| `destination`  | no       | destination namespace; `server` defaults to the role default |
| `syncPolicy`   | no       | deep-merged over the role default (`recursive=True`)         |
| `project`      | no       | AppProject, defaults to the role default                     |
| `wait`         | no       | per-application override of the global wait                  |

### `source` is opaque

`source` is ArgoCD's own `spec.source`, written through untouched. The role
never enumerates its keys, so **every** source form works — `chart`, `directory`,
`kustomize`, `plugin`, plain `path`, plus `repository` credentials for private
repos. A source format this role has never heard of costs no role change at all:
just write the keys into the fact file.

### Chart CRDs are the chart's business, not ArgoCD's

A chart whose CRDs are missing from the cluster while the app reports
`Synced`/`Healthy` is the most common way this role gets blamed for something
it did faithfully. Two separate traps, both hit live on rke21 (ArgoCD v3.5.3,
chart argo-cd 10.9.4):

**1. There is no ArgoCD-level switch that fixes a templated CRD.** ArgoCD 3.x
removed `helm.enableCRds` from the Application schema, and strict decoding
*silently* drops it rather than erroring. The replacement, `helm.skipCrds`, only
governs a chart's `crds/` **directory** — and the controller normalises it away
when it is `false` ("Error persisting normalized application spec" in the
application-controller log, `generation` bumps within a second of applying).
Neither field affects a chart that renders its CRDs as *templates*, which is
most of them nowadays: cert-manager's chart has no `crds/` directory at all.
The lever is the chart's own value — for cert-manager, `crds.enabled`, which
defaults to `false`:

```yaml
- name: cert-manager
  source:
    repoURL       : https://charts.jetstack.io
    chart         : cert-manager
    targetRevision: v1.21.2
    helm:
      valuesObject:
        crds:
          enabled: true
          keep   : true
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
  destination:
    namespace: cert-manager
```

A chart that ships CRDs the other way (external-secrets renders them as
templates already on by default) needs nothing — just confirm they appear.

**2. A post-install hook that checks the CRDs deadlocks the sync forever.**
cert-manager's `startupapicheck` Job carries `helm.sh/hook: post-install` and its
only job is to verify the cert-manager CRDs are installed. Inside one ArgoCD
application it waits for CRDs that the very same sync has not created yet, so
the sync never completes. Worse, **ArgoCD refuses to start any new sync while
an operation is in flight**, so the app is frozen: later edits to the fact file
are applied to the spec but never acted on, and the CRDs show as `Missing`
forever. Only deleting the Application clears it — the `status` subresource is
not patchable, so there is no way to terminate the operation in place. If an app
is stuck in `Running` and a values change appears to do nothing, delete it and
re-apply rather than re-running the role. Disabling the hook avoids the trap
entirely:

```yaml
        startupapicheck:
          enabled: false
```

A wedged `startupapicheck` Job also keeps its namespace in `Terminating`
indefinitely; if that happens, clear it with the finalize subresource:

```sh
kubectl replace --raw /api/v1/namespaces/cert-manager/finalize -f - <<< '{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"cert-manager"},"spec":{"finalizers":[]}}'
```

### Oversized CRDs need `ServerSideApply=true`

ArgoCD records what it applied in a `last-applied-configuration` annotation, and
annotations are capped at 262144 bytes. CRDs above that cap — external-secrets'
`secretstores` and `clustersecretstores` are both over it — fail the sync with
`metadata.annotations: Too long`, while the other ~60 CRDs in the same app
apply fine:

```
CustomResourceDefinition "secretstores.external-secrets.io" is invalid:
  metadata.annotations: Too long: may not be more than 262144 bytes
```

Server-side apply keeps the desired state in the managed-fields table instead of
an annotation, so it sidesteps the cap. Set it per application:

```yaml
  syncPolicy:
    syncOptions:
      - ServerSideApply=true
```

`spec.syncPolicy` is deep-merged over the role default, so declaring
`syncOptions` this way keeps the default `automated: {prune, selfHeal}` intact.

### Other source forms

Plain manifests from a git repo:

```yaml
- name: external-secrets
  source:
    repoURL      : https://raw.githubusercontent.com/external-secrets/external-secrets/main
    targetRevision: main
    path         : deploy/crds/bundle.yaml
    directory:
      recurse: true
  destination:
    namespace: external-secrets
```

Kustomize overlay, with a per-app sync policy and private-repo credentials:

```yaml
- name: platform-apps
  source:
    repoURL      : https://git.ctlabs.internal/infra/apps.git
    targetRevision: main
    path         : overlays/lab
    kustomize    : {}
    repository   :
      type: git
      repoURL  : https://git.ctlabs.internal/infra/charts.git
      username : argocd
      password : $repo-creds
  syncPolicy:
    automated:
      selfHeal: false
  destination:
    namespace: platform
```

Use `helm.valuesObject`, not `helm.values`, for nested values — it is a native
mapping in the object, so ints and booleans stay typed instead of degrading into
strings the way templated inline YAML does.

## Local Facts

Written to `/etc/ansible/facts.d/ctlabs_argocd_apps.fact`:

```json
{
  "namespace": "argo",
  "kubeconfig": "/etc/rancher/k3s/k3s.yaml",
  "interpreter": "/usr/sbin/ip vrf exec default /usr/bin/python3",
  "applications": [
    {
      "name": "cert-manager",
      "source": {
        "repoURL": "https://charts.jetstack.io",
        "chart": "cert-manager",
        "targetRevision": "v1.21.2",
        "helm": {
          "valuesObject": {
            "crds": { "enabled": true, "keep": true },
            "startupapicheck": { "enabled": false }
          }
        }
      },
      "syncPolicy": {
        "syncOptions": ["CreateNamespace=true", "ServerSideApply=true"]
      },
      "destination": { "namespace": "cert-manager" }
    }
  ]
}
```

Per-host resolution via `ctg_facts.ctlabs_argocd_apps.*` — fact is authoritative,
falls back to role defaults. Only knobs actually set for a host are written to
the fact file, so an absent key still reaches the role default.

## Tests

```sh
pytest -sv roles/ctlabs_argocd_apps/tests
```
