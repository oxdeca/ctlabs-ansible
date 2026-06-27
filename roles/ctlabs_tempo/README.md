# Ansible Role `ctlabs_tempo`

## Ansible Tags

- `ctlabs_tempo`
- `ctlabs_tempo.precheck`
- `ctlabs_tempo.package`
- `ctlabs_tempo.config`
- `ctlabs_tempo.service`

## Prechecks

- OS: debian12, centos9, redhat9

## Description

Installs Grafana Tempo — a high-volume, minimal-dependency distributed tracing backend — from the official GitHub release tarball. Runs in monolithic mode (`target: all`) with OTLP receivers and optional metrics-generator for span metrics and service graphs.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `versions.tempo` | `3.0.2` | Tempo release version |
| `ctlabs_tempo.defaults.server.http_listen_port` | `3200` | Tempo HTTP API port |
| `ctlabs_tempo.defaults.server.grpc_listen_port` | `9095` | Tempo gRPC port |
| `ctlabs_tempo.defaults.distributor.receivers.otlp.protocols.grpc.endpoint` | `0.0.0.0:4317` | OTLP gRPC receiver |
| `ctlabs_tempo.defaults.distributor.receivers.otlp.protocols.http.endpoint` | `0.0.0.0:4318` | OTLP HTTP receiver |
| `ctlabs_tempo.defaults.storage.backend` | `local` | Storage backend |
| `ctlabs_tempo.defaults.storage.local.path` | `/var/tempo/traces` | Local storage path |
| `ctlabs_tempo.defaults.storage.wal.path` | `/var/tempo/wal` | WAL path |
| `ctg_facts.ctlabs_tempo.metrics_generator` | `false` | Enable metrics-generator |

## Grafana Integration

A Tempo datasource is provisioned automatically by `ctlabs_grafana` (template: `tempo.yml.j2`). URL defaults to `http://localhost:3200` and is overridable via `ctg_facts.ctlabs.grafana.ds.tempo_url`.

## Tests

```sh
pytest -sv roles/ctlabs_tempo/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.
