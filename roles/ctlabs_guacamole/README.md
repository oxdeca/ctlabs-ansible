# Ansible Role `ctlabs_guacamole`

## Ansible Tags

- `ctlabs_guacamole`
- `ctlabs_guacamole.precheck`
- `ctlabs_guacamole.package`
- `ctlabs_guacamole.config`
- `ctlabs_guacamole.service`

## Prechecks

- Supported OS: `centos9` (`ctlabs_guacamole.os`)

## Config

### `user-mapping.xml` — facts-driven

`config.user_mapping.users` (`ctlabs_guacamole.defaults.config.user_mapping.users`) is a list of
Guacamole users, each with a list of connections, rendered into `/etc/guacamole/user-mapping.xml`.
Resolved in `precheck.yml` as `ctlabs_guacamole_users`, with local facts taking priority over the
role default (same pattern as the rest of the repo: `ctg_facts.<role>.<key>` > role default).

```yaml
ctlabs_guacamole_users:
  - username: ctlabs
    password: secret123!
    connections:
      - name: myhost
        protocol: ssh      # or vnc, rdp
        params:            # rendered as <param name="key">value</param>
          hostname: myhost
          port: 22
          username: root
```

`params` values that are booleans render as lowercase (`true`/`false`) to match Guacamole's
expected format.

### Local Facts

- `/etc/ansible/facts.d/ctlabs_guacamole.fact`

```json
{
  "users": [
    {
      "username": "ctlabs",
      "password": "secret123!",
      "connections": [
        {
          "name": "myhost",
          "protocol": "rdp",
          "params": {
            "hostname": "192.168.30.14",
            "port": 3389,
            "ignore-cert": true
          }
        }
      ]
    }
  ]
}
```

Set per-host via a lab's `play.setup` profile (`setup_profiles.yml`), keyed under the
`guacamole` profile the same way `ctlabs_kind`/`ctlabs_helm` per-host facts are keyed — see
`ctlabs/lib/lab.rb#generate_setup_yml`. If no `users` fact is set, the role falls back to its
default (single `ctlabs` user, a handful of lab connections) — same behavior as before this
change.
