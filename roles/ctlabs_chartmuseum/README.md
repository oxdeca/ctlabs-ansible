# Ansible Role `ctlabs_chartmuseum`

## Ansible Tags

- `ctlabs_chartmuseum`
- `ctlabs_chartmuseum.precheck`
- `ctlabs_chartmuseum.package`
- `ctlabs_chartmuseum.config`
- `ctlabs_chartmuseum.service`
- `ctlabs_chartmuseum.facts` (setup)

## Prechecks

- OS: redhat9, centos9, debian11, debian12
- Virtualization: any
- Architecture: `amd64`, `arm64`, `arm` — the only ones the helm project
  publishes a static binary for. Anything else fails in `precheck.arch.supported`.

## Description

Installs [ChartMuseum](https://chartmuseum.com) from the official static
release binary and runs it as `chartmuseum.service` under a dedicated
`chartmuseum` user. Configuration lives in a single viper-backed YAML file at
`/etc/chartmuseum/config.yml` (mode `0640`, group `chartmuseum`).

TLS is on by default using the ca-ctlabs node certificate, and basic auth
protects the write/API actions while leaving `GET index.yaml` anonymous so
`helm repo add` works without credentials.

## Configuration

The local fact (`/etc/ansible/facts.d/ctlabs_chartmuseum.fact`) is a **flat
config overlay**: its top-level keys map onto `defaults.config`, and they are
merged **recursively** over it. Setting only `auth.user` therefore keeps every
other default under `config.auth`. Note the fact file name supplies the
`ctlabs_chartmuseum` prefix, so the keys are *not* wrapped in a `config:` block.

```yaml
# /etc/ansible/facts.d/ctlabs_chartmuseum.fact
port: 8080
contextpath: /charts              # helm clients then use https://host:8080/charts
tls:
  enabled: true
  crt: /etc/ca-ctlabs/<node>.crt
  key: /etc/ca-ctlabs/<node>.prv
auth:
  enabled: true
  anonymous_get: true             # GET stays open, POST/PUT/DELETE need credentials
  user: ctlabs
  pass: secret123!
url: https://<node>:8080          # derived by facts.json.j2 for other roles
```

The `auth` block is **not** written into the fact file — that file is
world-readable, and the role re-reads `ctg_facts` at config-render time where
`/etc/chartmuseum/config.yml` is `0640` and the template task runs `no_log`.

| Variable                                        | Default                                     | Description                              |
|-------------------------------------------------|---------------------------------------------|------------------------------------------|
| `versions.chartmuseum`                          | `0.16.6`                                    | Release version                          |
| `...defaults.download.bindir`                   | `/opt/chartmuseum`                          | Install directory                        |
| `...defaults.download.bin`                      | `/opt/chartmuseum/chartmuseum`              | Symlink to the versioned binary          |
| `...defaults.config.datadir`                             | `/var/lib/chartmuseum`                      | Local storage backend root               |
| `...defaults.config.listen`                              | `0.0.0.0`                                   | Listen address                           |
| `...defaults.config.port`                                | `8080`                                      | Listen port                              |
| `...defaults.config.contextpath`                         | `''`                                        | Serve under a sub-path                   |
| `...defaults.config.charturl`                            | derived from nodename/port                  | Base URL written into `index.yaml` (no contextpath) |
| `...defaults.config.jsonindex`                           | `false`                                     | Render `index.yaml` body as JSON instead of YAML |
| `...defaults.config.allowoverwrite`                      | `false`                                     | Allow re-uploading a chart version       |
| `...defaults.config.disable_delete`                      | `false`                                     | Remove `DELETE /api/charts/<name>/<version>` |
| `...defaults.config.disable_api`                         | `false`                                     | Remove the `/api/*` routes entirely      |
| `...defaults.config.enable_metrics`                      | `true`                                      | Serve `/metrics`                         |
| `...defaults.config.max_upload_size`                     | `20971520`                                  | Max upload size in bytes                 |
| `...defaults.config.tls.enabled`                         | `true`                                      | Serve HTTPS                              |
| `...defaults.config.auth.enabled`                        | `true`                                      | Basic auth on write/API actions          |
| `...defaults.config.auth.anonymous_get`                  | `true`                                      | Leave `GET` anonymous                    |
| `...defaults.service.name`                      | `chartmuseum.service`                       | systemd unit                             |

## Verified behaviour (v0.16.6)

Traps confirmed against the real binary, worth knowing before changing anything:

- **The config file keys are viper keys, not CLI flag names.**
  `enablemetrics`, not `enable-metrics`. `json-index` and `maxuploadsize` do
  keep their hyphens.
- **`authanonymousget` must stay flat at the top level.** Nesting it under
  `auth:` is accepted silently and then does nothing — every `GET` returns 401.
- **The config file suffix must be `.yml`/`.yaml`**; anything else is rejected.
- **`storage.backend` is mandatory** — omitted, chartmuseum exits with
  `Missing required flags(s): --storage`.
- **`/health` is never basic-auth guarded** and follows `contextpath`. It is
  what the role's health check probes.
- **`/metrics` is always on the root** — it is *not* moved under `contextpath`,
  so probe it at `/metrics` regardless of the configured context path.
- **The only delete route is `DELETE /api/charts/<name>/<version>`** (name +
  version, no delete-by-name, no POST-style delete — those were pre-multitenant
  APIs). `disable_delete` drops it; `disable_api` drops the whole `/api/*` tree.
- **`tls.cacert` is a trap.** Setting it flips the listener to
  `RequireAndVerifyClientCert`, after which every client without a client cert
  — including the role's own health check — fails with
  `tls: client didn't provide a certificate`. It is left unset by design.
- **`charturl` must be absolute, and must NOT include `contextpath`.**
  chartmuseum builds `<charturl>/<contextpath>/charts/<name>-<version>.tgz`
  itself, so appending the contextpath in the role yields a doubled
  `/charts/charts/charts/...` path that 404s. It is derived per-host from
  nodename/port when not set explicitly.
- **`json-index` re-serializes `index.yaml` as JSON — it does not add an
  `/index.json` endpoint.** There is no such route in v0.16.6, and the response
  stays `Content-Type: application/x-yaml`. Consumers must still request
  `index.yaml`. Also note the cached index is only re-rendered when the repo
  changes, so toggling the flag alone leaves the old YAML body in place.
- **`/etc/ca-ctlabs/*.prv` is `0640 root:certs`**, so the service user is added
  to the `certs` group.

## Tests

```sh
pytest -sv roles/ctlabs_chartmuseum/tests
```

Validates template presence, `--syntax-check` of the role against a localhost
playbook, and pins the viper key spellings / the `tls.cacert` and auth-password
regressions described above.
