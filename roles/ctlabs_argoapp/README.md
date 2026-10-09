# Ansible Role `ctlabs_argoapp`

Declares ArgoCD `Application` objects — cert-manager, external-secrets, and
anything else you want reconciled by ArgoCD instead of by `helm`.

**This role does not install ArgoCD.** The `argo/argo-cd` chart is installed by
`ctlabs_helm`; this role only creates the `Application` CRs that ArgoCD then
manages. Play order matters: `ctlabs_helm` must run first.

With no applications declared the role is a complete no-op, so it is safe to
list on every cluster lab.

## Ansible Tags

| Tag                           | Targets                          |
|-------------------------------|----------------------------------|
| `ctlabs_argoapp`              | all role tasks                   |
| `ctlabs_argoapp.precheck`     | prechecks only                   |
| `ctlabs_argoapp.applications` | CRD wait + apply + health wait   |
| `ctlabs_argoapp.repositories` | repository credential Secrets    |
| `ctlabs_argoapp.facts`        | local facts write (setup play)   |

## Prechecks

- OS: centos8, centos9, redhat8, redhat9, debian11, debian12
- Each application has `name` and a `source` mapping containing at least `repoURL`
- Each repository has a unique `name` and a `url` (a duplicate name is the same
  Secret, so one repository would silently take another's credentials)
- **No application name may collide with a `ctlabs_helm` chart name** — Helm and
  ArgoCD must never manage the same release, or they revert each other forever
  and the app sits permanently `OutOfSync` with no obvious cause. The precheck
  reads `ctg_facts.ctlabs_helm.charts` and fails loudly on a conflict.
- **An ArgoCD control plane is actually there to target.** 
  The role depends on `ctlabs_helm` having installed `argo/argo-cd` *before* it runs, so a wrong play
  order or a wrong namespace must fail here — loudly — rather than as a mystery
  timeout deep in `applications.yml`. When `applications` is non-empty the
  precheck verifies, via `kubernetes.core.k8s_info` (no shell/kubectl):
  1. the `applications.argoproj.io` CRD is `Established` (fast 30 s fail-fast
     signal that complements the tolerant `crd_wait` loop that runs just before
     the apply), and
  2. an ArgoCD **application controller has ≥1 ready replica** in
     `defaults.namespace`, probing both a `Deployment` (helm chart) and a
     `StatefulSet` (operator) via label
     `app.kubernetes.io/component=application-controller`.

  The CRD check alone is not enough: an `Established` CRD outlives a
  failed/rolled-back install, and a dead controller means Applications are
  created, look fine in `kubectl get`, and are silently **never** reconciled —
  the run would report success while the cluster quietly stays `OutOfSync`. This
  closes that hole.

  With `applications: []` the role stays a **complete no-op** — these checks are
  all guarded on `applications | length > 0`, so no cluster contact at all.

## Configuration

| Variable                                     | Default                                             | Description                                                                                  |
|----------------------------------------------|-----------------------------------------------------|----------------------------------------------------------------------------------------------|
| `ctlabs_argoapp.defaults.namespace`      | `argo`                                               | ArgoCD control-plane **namespace** (Application CRs go here). `ctlabs_helm` deploys release `argocd` into namespace `argo` (`helm list -A`: NAME=`argocd`, NAMESPACE=`argo`) — the release *name* is not the namespace |
| `ctlabs_argoapp.defaults.kubeconfig`     | `""`                                                | `KUBECONFIG` path; empty = controller default                                                |
| `ctlabs_argoapp.defaults.interpreter`    | `""`                                                | `ansible_python_interpreter` override, e.g. `/usr/sbin/ip vrf exec default /usr/bin/python3` |
| `ctlabs_argoapp.defaults.project`        | `default`                                           | default ArgoCD AppProject                                                                    |
| `ctlabs_argoapp.defaults.server`         | `https://kubernetes.default.svc`                    | default destination API server                                                               |
| `ctlabs_argoapp.defaults.sync_policy`    | automated (prune, selfHeal, `CreateNamespace=true`) | default `spec.syncPolicy`                                                                    |
| `ctlabs_argoapp.defaults.finalizers`     | `[resources-finalizer.argocd.argoproj.io]`          | cascade-delete resources on Application removal; `[]` keeps them                             |
| `ctlabs_argoapp.defaults.wait`           | `true`                                              | wait for `Synced` + `Healthy` after apply                                                    |
| `ctlabs_argoapp.defaults.wait_timeout`   | `600`                                               | wait budget for an app still rolling out (seconds)                                          |
| `ctlabs_argoapp.defaults.wait_delay`     | `10`                                                | poll interval while waiting                                                                  |
| `ctlabs_argoapp.defaults.settle_retries` | `6`                                                | polls before concluding an app is merely rolling out; see [Failing fast](#failing-fast-on-bad-credentials) |
| `ctlabs_argoapp.defaults.error_conditions` | `[ComparisonError, SyncError, InvalidSpecError, DeletionError]` | ArgoCD condition types that mean "cannot reconcile", not "still working"   |
| `ctlabs_argoapp.defaults.transient_errors` | connectivity substrings (see [Transient errors](#transient-errors-wait-dont-fail)) | error **messages** that mean "not ready yet", not "misconfigured" — these are waited out instead of failed |
| `ctlabs_argoapp.defaults.crd_wait`       | `300`                                               | wait for the `applications.argoproj.io` CRD                                                  |
| `ctlabs_argoapp.defaults.applications`   | `[]`                                                | applications to declare (normally supplied per host as a local fact)                         |
| `ctlabs_argoapp.defaults.repositories`   | `[]`                                                | git/helm repositories ArgoCD may fetch, with credentials (see below)                        |

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

### This role installs apps; it does not configure them

> Full worked examples — a Cloudflare DNS-01 `ClusterIssuer`, a Vault-backed
> `ClusterSecretStore` on vdb1, and the matching facts entry for both — are in
> **[`docs/config-examples.md`](docs/config-examples.md)**. Every snippet there
> was run against the live rke21 cluster.

The role's job ends at "cert-manager and external-secrets are running". What
you then want — a `ClusterIssuer` doing a Cloudflare DNS-01 challenge, a
`ClusterSecretStore` pointed at Vault — is **not** an ArgoCD Application and does
not belong in the `applications:` list. Those are plain custom resources that
cert-manager and external-secrets each define and watch; there is no chart, no
version to pin, and nothing to reconcile upstream.

The distinction that keeps this sane:

|                | installed by this role                         | configured by                                                                  |
|----------------|------------------------------------------------|--------------------------------------------------------------------------------|
| what           | cert-manager, external-secrets, … the operator | `Issuer`/`ClusterIssuer`, `SecretStore`/`ClusterSecretStore`, `ExternalSecret` |
| shape          | ArgoCD `Application` → chart                   | the operator's own CRs, versioned in git                                       |
| who reconciles | ArgoCD                                         | whoever owns the config — usually ArgoCD again, via a *second* Application     |

So there are two defensible ways to manage the config half, and they are not
exclusive:

1. **App-of-apps (recommended, most GitOps-idiomatic).**
   Put the `Issuer` and `ClusterSecretStore` YAML in a git repo and add *one more* Application to the facts pointing at that directory. 
   Same role, same passthrough, no new mechanics — a `directory`/`kustomize` source is already supported (see the render test).
   Secrets referenced by them stay out of git; only the reference is committed. Verified on rke21: the ArgoCD application-controller
   can create cluster-scoped `clusterissuers.cert-manager.io` and `clustersecretstores.external-secrets.io`, so the default project is not a blocker.
2. **A second role**
   (e.g. `ctlabs_cert_manager`, `ctlabs_external_secrets`) that declares those CRs directly.
   Fine if you want Ansible to own them, but it re-introduces imperative drift-tolerance concerns and duplicates git's
   job — prefer (1) unless you need the CRs before ArgoCD is up.

Do **not** bolt config onto the install by adding the operator's CRs to the chart's `valuesObject`: that only works for charts that happen to template them,
and it ties your DNS/Vault topology to a chart's release cycle.

Two version traps in the config layer, both hit live on rke21 with external-secrets 2.11.0:

- **`apiVersion` must be `external-secrets.io/v1`, not `v1beta1`.** 
  The CRD still lists `v1beta1` in `spec.versions`, but with `served: false` — so copy-pasted docs and older examples fail with
  `no matches for kind "ClusterSecretStore" in version "external-secrets.io/v1beta1"`.
  Check `kubectl get crd clustersecretstores.external-secrets.io -o jsonpath='{.spec.versions[*].name}'` together with the `served` flag; the name alone lies.
- **cert-manager's `selector` is a sibling of `dns01`, not a child of it.**
  Nesting it inside `dns01` fails with a strict-decoding error naming the exact field. `kubectl apply --dry-run=server` validates all of this without
  creating anything, which is the cheap way to check a config CR before it goes anywhere near git.

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

Kustomize overlay, with a per-app sync policy. Credentials come from
`repositories` (below), not from the Application:

```yaml
- name: platform-apps
  source:
    repoURL      : https://git.ctlabs.internal/infra/apps.git
    targetRevision: main
    path         : overlays/lab
    kustomize    : {}
  syncPolicy:
    automated:
      selfHeal: false
  destination:
    namespace: platform
```

Use `helm.valuesObject`, not `helm.values`, for nested values — it is a native mapping in the object, so ints and booleans stay typed instead of degrading into strings the way templated inline YAML does.

## Repository credentials

ArgoCD does **not** accept credentials on the Application. It discovers them
from Secrets in its own namespace carrying the label
`argocd.argoproj.io/secret-type: repository`. Without such a Secret, an
application pointing at a private repo is created perfectly happily and then
fails every sync with an auth error — nothing in `spec` can fix that.

`defaults.repositories` is what creates those Secrets:

```yaml
repositories:
  - name    : ctlabs-git
    type    : git
    url     : https://git1.ctlabs.internal:3000/ctlabs/cluster-config.git
    username: ctlabs
    password: secret123!
    insecure: true              # repo server serves a self-signed ctlabs_ca cert
    forceHttpBasicAuth: true
  - name: infra-ssh
    url : ssh://git@git1.ctlabs.internal:2222/ctlabs/infra.git
    sshPrivateKey: |
      -----BEGIN OPENSSH PRIVATE KEY-----
      ...
      -----END OPENSSH PRIVATE KEY-----
```

The application then references only the URL:

```yaml
- name: lab-issuers
  source:
    repoURL       : https://git1.ctlabs.internal:3000/ctlabs/cluster-config.git
    targetRevision: main
    path          : clusters/rke201
    directory:
      recurse: true
```

| Field                   | Purpose                                                                       |
|-------------------------|-------------------------------------------------------------------------------|
| `name`                  | Secret name; must be unique per repository                                    |
| `url`                   | must match the `source.repoURL` of the application using it                   |
| `type`                  | `git` (default), `helm`, `oci`                                               |
| `username` / `password` | HTTPS basic auth                                                              |
| `sshPrivateKey`         | SSH auth, PEM content                                                         |
| `bearerToken`           | HTTP bearer token                                                             |
| `insecure`              | skip the repo server's **TLS verification** — for the self-signed ctlabs_ca certs the lab git host serves. The alternative is mounting that CA into `argocd-repo-server` |
| `forceHttpBasicAuth`    | skip auth-method negotiation, force basic auth                               |
| `enableLfs`, `enableOCI`, `project`, `proxy`, `noProxy`, `tlsClientCertData` | passed through when set |

Notes:

- **Keys are allowlisted.** ArgoCD silently ignores `stringData` keys it does not
  recognise, so an unfiltered splat would turn a typo (`insecure_ssl`) into a
  mystery TLS failure at sync time rather than an error. Unknown keys are dropped.
- **Booleans are stringified.** `stringData` values must be strings; the API
  server rejects a real YAML boolean.
- **Applied before the applications.** The Secrets must exist before an
  application naming the repo is created, so `repositories` is also tagged
  `ctlabs_argoapp.applications` — a `-t ctlabs_argoapp.applications` run still
  creates the credentials its apps need.
- **Empty list is a complete no-op**, like `applications`.
- **Where the repo lives is out of scope.** ArgoCD's repo-server is a pod, so
  the repository must be reachable from the cluster's *data* network; the
  ansible controller's management address is not reachable from a pod (no VRF
  awareness in the pod network). `git://` needs no credentials at all and so
  needs no entry here.

### Secrets policy

Credentials are stored **in plaintext in the local fact file**
(`/etc/ansible/facts.d/ctlabs_argoapp.fact`), the same way `ctlabs_gitea` keeps
its own. Acceptable for a lab; anything shared or long-lived should come from
`ctlabs_vault` instead. A vault-backed variant (read the password at apply time
so it never lands in a fact file) is a deliberate non-goal for now.

## Vault CA ConfigMap

`cert-vault-sync` needs the lab CA (`/etc/ca-ctlabs/ca-ctlabs.crt`, written by
`ctlabs_ca` on every host) inside the cluster as a ConfigMap — historically a
manual `kubectl create configmap` step at lab-up.

This role no longer publishes it. The ConfigMap is now created by the **cluster
setup role** (`ctlabs_rke2`, `ctlabs_k8s`, `ctlabs_k3s`, `ctlabs_kind`,
`ctlabs_minikube`) through their generic `ca_configmaps` knob, applying before
any Argo apps sync. Each entry is `{ name, namespace, key, file? }` with `file`
defaulting to `/etc/ca-ctlabs/ca-ctlabs.crt`:

```yaml
ca_configmaps:
  - name     : ca-ctlabs-crt
    namespace: security-tools
    key      : ca.crt
```

The chart reads it via `caProvider` / `secretStores.vault.ca.configMapName`
(helm side creates it additively; the old `cert-vault-sync-vault-ca` ConfigMap
is removed after sync). Deployment contract is unchanged from the former
`ctlabs_argoapp.vault_ca`: declarative modules only (no kubectl/command), the
PEM is slurped on the node with `become: true`, and the namespace is created
if absent.

## Failing fast on bad credentials

A wrong credential is the failure mode this role is most likely to cause, and
ArgoCD makes it awkward to detect:

- The Application goes to `sync.status=Unknown` with a `ComparisonError`
  condition — but `health.status` **stays `Healthy`**.
- Health stays Healthy because with no target state there is nothing to compare
  against, so there is nothing to prune. Verified on rke21 with
  `automated.prune: true`: the running pod stayed `Running`. A broken credential
  does **not** harm workloads; it blocks reconciliation of every application on
  that repository while looking perfectly healthy.

So a naive `until: sync is Synced and health is Healthy` never becomes true. It
burns the whole `wait_timeout` (600s per application) and then reports something
useless, with the real cause visible only in the ArgoCD UI.

This role therefore reads all Applications in one pass and watches for a
*definitive* outcome before falling back to the long wait:

| phase | budget | purpose |
|---|---|---|
| `settle` | `settle_retries` × `wait_delay` (default 60s) | wait for all declared apps to reach `Synced`+`Healthy`, or for ArgoCD to state it cannot |
| `wait` | `wait_timeout` (default 600s) | for anything still genuinely rolling out |

If any Application lands on `sync.status=Unknown`, or carries a condition whose
`type` is in `error_conditions`, the run fails immediately, quoting ArgoCD's own
message:

```
ArgoCD cannot reconcile: ctlabs-scratch-gb [sync=Unknown, health=Healthy] Failed to
load target state: ... authentication required: Invalid username or token. ...
```

### Transient errors: wait, don't fail

The condition type alone is **not** proof of a misconfiguration. ArgoCD reports
every failure to produce manifests as `ComparisonError` + `sync.status=Unknown`,
including the ones that fix themselves. Measured on rke21 during lab bring-up,
the repo-server's very first `helm pull` of a public chart failed while pod
networking was still coming up:

```
external-secrets [sync=Unknown, health=Healthy] Failed to load target state:
failed to generate manifest for source 1 of 1: rpc error: code = Unknown
desc = error fetching chart: ... `helm pull --repo
https://charts.external-secrets.io external-secrets` failed: Get
"https://charts.external-secrets.io/index.yaml": dial tcp
[2607:f8b0:4023:1803::79]:443: connect: network is unreachable
```

That aborted the run — and the applications then converged on their own within
seconds, `cert-manager` and `external-secrets` both ending up `Synced`+`Healthy`.

So the **message** decides, not the condition type. If the concatenated condition
messages contain any substring in `transient_errors`, the Application is not
failed on, not rolled back, and simply falls through to the long `wait`, where a
rollout belongs anyway. Credential problems match none of those patterns, so the
fast fail and its rollback are unchanged:

| kind | examples | outcome |
|---|---|---|
| connectivity / fetch | `error fetching chart`, `dial tcp`, `network is unreachable`, `no such host`, `i/o timeout`, `context deadline exceeded`, `connection refused`, … | waited out |
| configuration | `authentication required`, `Invalid username or token`, `repository not found`, `permission denied`, chart version `not found` | fails fast, credentials rolled back |

`failed to generate manifest` is in the list deliberately: it is the umbrella for
a helm/render failure, so a genuinely bad manifest config costs `wait_timeout`
before failing instead of failing in 15s. The cost is time, never a false green.
Set `transient_errors: []` per host to make every error definitive again.

If a transient error does *not* recover, the long wait's own report quotes the
message ArgoCD gave, so that failure explains itself too.

Two mechanisms that look correct and are not, both measured rather than assumed:

- **`failed_when` does not fire between `until` retries.** It is only evaluated
  once the retries are exhausted, so it saves nothing (measured: 82s against a
  60s budget). The "errored" test has to live *inside* the `until` condition,
  which is re-evaluated per attempt.
- **Conditions are matched on `type`, never on `status`.** ArgoCD omits the
  `status` key entirely on a `ComparisonError`, so the obvious
  `selectattr('status', 'equalto', 'True')` raises
  `'dict object' has no attribute 'status'` — against a dict that obviously has
  the fields you want.

### Rollback

If the reconcile fails for a credential the role just wrote, the role undoes its
own change: a Secret it created is deleted, a Secret it modified is restored to
the exact prior bytes.

- Triggered **only** from the definitive-error path. Rolling back after an
  unrelated failure (a precheck that a narrow tag left without facts, say) would
  revert good credentials for no reason.
- Deliberately **not** a `block`/`rescue` around the whole role. A rescue makes
  the play succeed — measured: `ok=23 failed=0 rescued=1`, a bad credential
  reported as a *green* run. Rolling back from the fail-fast path keeps the recap
  honest (`failed=1`).
- Only Secrets listed in `repositories` are touched. Anything the role did not
  touch is left alone, including credentials that predate it.
- No-op when the run changed no credential — restoring identical bytes would be
  pointless, and deleting a pre-existing Secret would be destructive.

Restoring credentials restores the ability to reconcile. It does not repair the
already-`Unknown` Application: once the credential is correct it still needs a
sync (or a hard refresh, if ArgoCD is serving a cached manifest).

## Local Facts

Written to `/etc/ansible/facts.d/ctlabs_argoapp.fact`:

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

Per-host resolution via `ctg_facts.ctlabs_argoapp.*` — fact is authoritative, falls back to role defaults. Only knobs actually set for a host are written to the fact file, so an absent key still reaches the role default. The forward list is `_knobs` in `templates/facts.json.j2` (`namespace`, `kubeconfig`, `interpreter`, `project`, `server`, `wait`, `wait_timeout`, `crd_wait`, `sync_policy`, `finalizers`, `repositories`, `transient_errors`) plus `applications`.

## ctlabs play.setup (install cert-manager and external-secrets)
```yml
argoapp:
  hosts: [rke21]
  namespace: argo
  kubeconfig: /etc/rancher/rke2/rke2.yaml
  interpreter: /usr/sbin/ip vrf exec default /usr/bin/python3
  applications:
    - name: cert-manager
      source:
        repoURL: https://charts.jetstack.io
        chart  : cert-manager
        targetRevision: v1.21.2
        helm:
          valuesObject:
            crds:
              enabled: true
              keep   : true
            startupapicheck:
              enabled: false
      syncPolicy:
        syncOptions:
          - CreateNamespace=true
          - ServerSideApply=true
      destination:
        namespace: cert-manager
    - name: external-secrets
      source:
        repoURL: https://charts.external-secrets.io
        chart  : external-secrets
        targetRevision: 2.11.0
      syncPolicy:
        syncOptions:
          - CreateNamespace=true
          - ServerSideApply=true
      destination:
        namespace: external-secrets
```

The block above is the explicit `play.setup.argoapp` form. The standard,
profile-based form splits it across **two** lab files that must agree on the
profile name:

- `role_profiles.yml` declares the profile (`argoapp:` with `role`, `tags`, `hosts`)
- `setup_profiles.yml` holds the data, keyed by the **same short name** — `defaults:`
  for every host, node-name keys (`rke21:`) for per-host overrides

```yml
# role_profiles.yml
argoapp:
  role: ctlabs_argoapp
  tags: [argoapp]
  hosts: [rke21]

# setup_profiles.yml
argoapp:
  role: argoapp
  defaults:
    namespace  : argo
    interpreter: /usr/sbin/ip vrf exec default /usr/bin/python3
    applications:
      - name: cert-manager
        source:
          repoURL: https://charts.jetstack.io
          chart  : cert-manager
          targetRevision: v1.21.2
          helm:
            valuesObject:
              crds:
                enabled: true
                keep   : true
              startupapicheck:
                enabled: false
        syncPolicy:
          syncOptions:
            - CreateNamespace=true
            - ServerSideApply=true
        destination:
          namespace: cert-manager
  rke21:
    kubeconfig: /etc/rancher/rke2/rke2.yaml
```

**The block key in `setup_profiles.yml` MUST match the `role_profiles.yml`
profile name (`argoapp`).** Keyed `ctlabs_argoapp` instead, `lab.rb`'s
`build_play_setup` silently ignores it: no fact is written, the role runs on its
defaults, and it no-ops while looking perfectly healthy. The fact file itself is
still `/etc/ansible/facts.d/ctlabs_argoapp.fact` and precheck reads
`ctg_facts.ctlabs_argoapp.*` — only the setup_profiles *block key* is the short
name.

Hosts in the profile need the lab's ansible play to carry the `argoapp` tag (add
it to the lab play's `tags:` and let the playbooks regenerate — they're written
as part of `lab up`), then:

```sh
ansible-playbook playbooks/ctlabs.yml -t argoapp
```

`ctlabs_helm` must run first (ideally via `-t helm`) so the ArgoCD chart exists;
the role only applies Applications.

## Tests

```sh
pytest -sv roles/ctlabs_argoapp/tests
```
