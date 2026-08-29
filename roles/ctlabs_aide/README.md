# Ansible Role `ctlabs_aide`

Deploys and configures [AIDE](https://aide.github.io/) (Advanced Intrusion Detection Environment) — a host-based file integrity checker. A baseline database of critical system files is created and compared on a daily schedule via a systemd timer.

## Ansible Tags

- `precheck`
- `package`
- `config`
- `service`

## Prechecks

- OS: redhat9, centos9, debian11, debian12, kali2025, kali2026, parrot7

## Config

- Main configuration: `/etc/aide/aide.conf` (Debian) or `/etc/aide.conf` (RedHat), templated from `aide.conf.j2`.
- Database directory: `/var/lib/aide/`
  - Active database: `/var/lib/aide/aide.db`
  - Newly-generated database: `/var/lib/aide/aide.db.new`
- Reports: `/var/log/aide/aide.log`
- Additional selection lines can be injected via `ctg_facts.ctlabs_aide.config.extra` (per-host local fact) or the `ctlabs_aide_extra` variable. Each line is written verbatim into the config (e.g. `!/var/lib/foo` or `/opt/app NORMAL`).

### Behavior

- On first run (no baseline database), the role initializes and promotes the database automatically.
- If the config template changes, the `ctlabs_aide.handlers.db.reinit` handler regenerates the baseline so checks compare against the new config.

## Service

- `aide-check.service` — oneshot unit running a wrapper (`/usr/local/sbin/aide-check.sh`) that executes `aide --check`.
- `aide-check.timer` — runs the check daily at `03:15`, `Persistent=true` (missed runs execute after boot) with a randomized delay to avoid synchronized load across many hosts.

### Result surfacing (journald → log pipeline)

`aide --check` writes its full report to `/var/log/aide/aide.log`. The wrapper also surfaces the **outcome** to the journal via `logger` with identifier `aide-check`, mapping aide's exit codes:

| aide rc | meaning                     | journald log                              | service state |
|---------|-----------------------------|-------------------------------------------|---------------|
| 0       | no differences              | `OK (no differences)`                     | ok            |
| 5       | differences found           | `differences found (aide rc=5)` (warning) | ok (exit 0)   |
| 1/6/7/… | real error (db/corrupt/etc) | `FAILED (aide rc=N)` (error)              | failed        |

Because the ctlabs hosts ship journald to Loki (via Alloy/promtail), these entries are automatically available centrally for dashboards/alerting. Note that "differences found" (rc=5) is treated as a **warning** and does not fail the unit — only genuine errors fail it, so a normal change in monitored files doesn't look like a service crash.

Run a manual check:
```sh
systemctl start aide-check.service
journalctl -u aide-check.service -n 50
```

## Tests

```sh
pytest -sv roles/ctlabs_aide/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.
