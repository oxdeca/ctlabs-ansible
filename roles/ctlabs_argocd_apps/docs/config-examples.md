# Configuring cert-manager / external-secrets with `ctlabs_argocd_apps`

`ctlabs_argocd_apps` **installs the operators**. 
  Their configuration is not an ArgoCD Application and does not belong in the same `applications:` list 
    — an `Issuer` or a `ClusterSecretStore` is a plain custom resource that cert-manager / external-secrets each define and watch.

The split, and the mechanism for the second half:

|                | installed by this role            | configured by                                           |
|----------------|-----------------------------------|---------------------------------------------------------|
| what           | cert-manager, external-secrets, … | `ClusterIssuer`, `ClusterSecretStore`, `ExternalSecret` |
| where it lives | the `applications:` list in facts | a **git repo**                                          |
| who reconciles | ArgoCD                            | ArgoCD, via **one more Application**                    |

So we add exactly **one** more entry per config repo. No second role, no role change: `spec.source` is verbatim passthrough, so a `directory` source works exactly like a `chart` one.

---

## 1. The git repo

```
config-repo/
└── clusters/
    └── lab-issuers/                      # one directory = one ArgoCD Application
        ├── 00-cluster-issuer.yaml
        ├── 10-certificate.yaml
        ├── 20-clustersecretstore.yaml
        └── 30-externalsecret.yaml
```

**Only references go in git — never secret material.** 
  The Cloudflare token and the Vault password are `secretRef`s pointing at Kubernetes Secrets that some *other* mechanism creates (here: `ctlabs_vault`, or a SOPS/`sealed-secrets` step).

---

## 2. cert-manager: a Cloudflare DNS-01 `ClusterIssuer`

```yaml
# clusters/lab-issuers/00-cluster-issuer.yaml
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@ctlabs.internal
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
      - dns01:
          cloudflare:
            apiTokenSecretRef:
              name: cloudflare-api-token
              key: token
        selector:                    # <-- SIBLING of dns01, NOT nested inside it
          dnsZones:
            - ctlabs.internal
```

**`selector` is a sibling of `dns01`, not a child.** 
  Nesting it inside `dns01` fails with a strict-decoding error that names the field:

```
strict decoding error: unknown field "spec.acme.solvers[0].dns01.selector"
```

Use a **`ClusterIssuer`** (not a namespaced `Issuer`) if you want per-zone solver selection — only cluster-scoped issuers can use `dnsZones`.

Then request a certificate:

```yaml
# clusters/lab-issuers/10-certificate.yaml
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: api-tls
  namespace: lab-apps
spec:
  secretName: api-tls
  dnsNames:
    - api.ctlabs.internal
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
```

### The facts entry — one Application per config directory

```yaml
# in the argocd: profile block
argocd:
  namespace  : argo
  kubeconfig : /etc/rancher/rke2/rke2.yaml
  interpreter: /usr/sbin/ip vrf exec default /usr/bin/python3
  applications:
    # ... the operators themselves ...

    - name: lab-issuers
      source:
        repoURL       : git://192.168.30.41:9418/config-repo.git
        targetRevision: main
        path          : clusters/lab-issuers
        directory:
          recurse     : true
      syncPolicy:
        syncOptions:
          - CreateNamespace=true
          - ServerSideApply=true
      destination:
        namespace: default
```

This is **live-verified** on rke21: the app goes `Synced`/`Healthy` and the
`ClusterIssuer` reports `READY=True`.

> **Give these config apps the resources finalizer.** Without it, deleting the
> Application orphans the CRs. The role's `finalizers` default already covers
> this, but if you set `finalizers: []` on the `argocd:` block you'll lose it.
> Even *with* the finalizer, a `Certificate`'s Secret can outlive the app (the
> ownerRef is on the Certificate, not the Secret) — expect to prune those by hand.

---

## 3. external-secrets: a Vault-backed `ClusterSecretStore`

Wired against the real vault on **vdb1** and verified working.

### The two prerequisite Secrets (NOT in git)

```sh
# the CA, so external-secrets can verify vault's TLS cert
kubectl -n external-secrets create configmap vault-ca-bundle \
  --from-file=ca.crt=/etc/ca-ctlabs/ca-ctlabs.crt

# the vault password — ctlabs_vault owns this, not git
kubectl -n external-secrets create secret generic vault-creds \
  --from-literal=password='secret123!'
```

### The store

```yaml
# clusters/lab-issuers/20-clustersecretstore.yaml
---
apiVersion: external-secrets.io/v1          # NOT v1beta1 — see below
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "https://vdb1.ctlabs.internal:8200"
      path:   "secret"
      version: "v2"
      caProvider:                            # flat — NOT nested under configMap:
        type:      ConfigMap
        name:      vault-ca-bundle
        key:       ca.crt
        namespace: external-secrets
      auth:
        userPass:                             # capital P
          username: ctlabs
          secretRef:                          # no inline password, ever
            name:      vault-creds
            key:       password
            namespace: external-secrets
```

> **Do not set `auth.userPass.path`.** It's optional and the client already
> prefixes `auth/userpass/login`. Setting it yields a doubled path and a
> baffling 403:
> ```
> URL: PUT https://vdb1.ctlabs.internal:8200/v1/auth/auth/userpass/login/login/ctlabs
> Code: 403. permission denied
> ```

### Pulling a secret into the cluster

```yaml
# clusters/lab-issuers/30-externalsecret.yaml
---
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: db-credentials
  namespace: default
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: db-credentials
    creationPolicy: Owner
  data:
    - secretKey: username
      remoteRef:
        key: lab/db
        property: username
    - secretKey: password
      remoteRef:
        key: lab/db
        property: password
```

Live-verified: `Ready=True secret synced`, the k8s Secret gets the values, and
**rotating the value in vault propagates to the k8s Secret** — that's real
continuous sync, not a one-time copy.

---

## Schema traps, all hit live against external-secrets 2.11.0

| wrong | right | symptom |
|---|---|---|
| `apiVersion: external-secrets.io/v1beta1` | `external-secrets.io/v1` | `no matches for kind "ClusterSecretStore" in version "external-secrets.io/v1beta1"` — 2.11.0 has `v1beta1` at `served: false` |
| `caProvider: {configMap: {...}}` | `caProvider: {type, name, key, namespace}` | `unknown field "spec.provider.vault.caProvider.configMap"` |
| `auth.userpass` | `auth.userPass` | `unknown field ... auth.userpass` |
| `auth.userPass.path: auth/userpass/login` | omit it | 403 on `auth/auth/userpass/login/login/ctlabs` |

The CRD still *lists* `v1beta1` in `spec.versions`, so eyeballing the version
list lies — check the `served` flag:

```sh
kubectl get crd clustersecretstores.external-secrets.io \
  -o jsonpath='{.spec.versions[*].name}{"\n"}{.spec.versions[*].served}{"\n"}'
```

**Always dry-run a config CR before committing it** — validates against the
real CRD, creates nothing:

```sh
kubectl apply -f clusterissuer.yaml --dry-run=server
```

---

## Networking: where the git host (and vault) must live

Pods have **no VRF awareness** — they egress via the main table, so they cannot
reach `192.168.99.0/24` (the management network) at all. Anything ArgoCD or
external-secrets fetches must be internet-reachable or on a **data-plane**
address.

Vault on vdb1 is `192.168.30.11:8200`, and pods resolve
`vdb1.ctlabs.internal` → `192.168.30.11` via cluster DNS, which is why the store
uses the **name** rather than the IP: vault's serving certificate has
`DNS:vdb1.ctlabs.internal` in its SAN but `api_addr` is the bare IP, so an
IP-based `server:` fails TLS verification.

> Testing note: a `busybox` pod reaching vault gives `TLS error (alert 47)`. That
> is **not** a network fault — busybox's TLS stack is too weak for vault's
> TLSv1.3. `curl`/`openssl` from the same pod network work fine. Don't chase it.
