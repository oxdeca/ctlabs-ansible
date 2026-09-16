# Ansible Role `ctlabs_k8s`

Sets up a single- or multi-node Kubernetes cluster with `kubeadm`, including CNI (calico/flannel/weave) and kube-vip. The Kubernetes version is pinned in `versions.k8s` (default `1.36.4`).

## Node Roles

Each node runs the role with one of three roles (`ctlabs_k8s_role`, resolved via local facts — see below):

| Role     | kubeadm action                       | Notes                                                        |
|----------|--------------------------------------|--------------------------------------------------------------|
| `master` | `kubeadm init` with `--upload-certs` | Initial control plane. Runs CNI install + kubelet CSR approval. Writes the join payload. |
| `control`| `kubeadm join --control-plane`       | Additional control-plane members; consumes the master's certificate-key. |
| `worker` | `kubeadm join`                       | Worker node.                                                 |

A node's role is set through the per-host `ctlabs_role_facts` (`role`, plus `master_node`/`master_ip` for join nodes) which `facts.yml` writes to `ctg_facts.ctlabs_k8s`; the role defaults to `master`.

How joining works:

1. The master generates the bootstrap token + certificate-key **once** into `/etc/kubernetes/ctlabs_k8s_secrets.yml` (`stat`-guarded, so re-runs keep a stable token).
2. After `kubeadm init` the master computes the cluster CA hash and renders `/etc/kubernetes/ctlabs_k8s_join.yml`.
3. `control`/`worker` nodes wait for `master_ip:6443`, then `slurp` the join file from the master (`delegate_to` the master node, with retries for the bootstrap race) and render their `kubeadm-join.yml` from it.
4. `control` nodes include the `controlPlane` + `certificateKey` block; `worker` nodes do not.

`ctlabs_k8s_master_ip` must point at the first control-plane node (it is also the advertise/local API endpoint beaconing host). See the k8s groups in `role_profiles.yml` for an example 1-master/2-control multi-node layout.

> Components that used to be deployed via raw manifests (ingress/traefik) now come from Helm charts owned by [`ctlabs_helm`](../ctlabs_helm/README.md) — see the cluster's `helm` profile in `setup_profiles.yml`.

## Storage

The storage engine is **cluster-wide** and decided by the **master only**. Set it on the `master` host of the lab's `k8s:` profile via `ctg_facts.ctlabs_k8s.storage`:

| Value      | Engine                                                             | Deployed by |
|------------|--------------------------------------------------------------------|-------------|
| `local`    | `rancher/local-path-provisioner` — one Deployment + a default StorageClass, node-local paths under `data_dir` (default `/media/vols`) | this role (master, raw manifest) |
| `longhorn` | Longhorn (replicated storage) — requires the `longhorn/longhorn` chart added to the `helm` profile of an opt-in lab; this role is a no-op | `ctlabs_helm` |
| `none`     | No storage engine                                                | —           |

> Putting `storage` on any non-`master` host fails the role's precheck — both engines install cluster-wide, so a per-host value would be inconsistent. Switch engines by changing the value on the master (default `local` when unset).

Use `local` for minimal footprint labs (a `2G` worker is fine — there is no per-node DaemonSet). Use `longhorn` only when a lab must exercise replication; to keep a node out of Longhorn scheduling set its fact to `none` and add a node `allowScheduling: false` resource in the lab's helm chart config.

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
| `ctlabs_k8s_role`                         | `master`    | Node role: `master`, `control`, or `worker`     |
| `ctlabs_k8s_master_ip`                    | node IP     | Control plane advertise address                 |
| `ctlabs_k8s_pod_cidr`                     | `10.8.0.0/16` | Pod network subnet (must fit one `/24` per node; `/16` for multi-node, `/24` is single-node only) |
| `ctlabs_k8s.defaults.config.network`      | `calico`    | CNI (`calico`, `flannel`, `weave`)             |
| `ctlabs_k8s.defaults.config.lb`           | `kube-vip`  | Services LoadBalancer (one at a time): `kube-vip` (host IP), `metallb`, `none` |
| `ctlabs_k8s.defaults.config.storage.engine` | `local`   | Storage engine: `local` (default), `longhorn`, `none` |

## Tests

```sh
pytest -sv roles/ctlabs_k8s/tests
```
