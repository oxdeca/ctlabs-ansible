# Ansible Role `ctlabs_postfix`

## Ansible Tags

- `ctlabs_postfix`
- `ctlabs_postfix.precheck`
- `ctlabs_postfix.package`
- `ctlabs_postfix.config`
- `ctlabs_postfix.service`
- `ctlabs_postfix.helper`
- `ctlabs_postfix.dkim`

## Prechecks

- OS: redhat7, redhat8, redhat9, centos7, centos8, centos9

## Configuration

Variables are resolved with the following precedence (highest first):

1. `ctg_facts.ctlabs_postfix.<key>` — local fact on the host
2. `<flat_var>` — playbook / extra var
3. `ctlabs_postfix.defaults.dkim.<key>` — role default

| Fact / Var                                 | Default                         | Description                            |
|--------------------------------------------|---------------------------------|----------------------------------------|
| `ctg_facts.ctlabs_postfix.dkim.enable`     | `false`                         | Enable dkimpy-milter DKIM signing      |
| `ctg_facts.ctlabs_postfix.dkim.selector`   | `default`                       | DKIM DNS selector                      |
| `ctg_facts.ctlabs_postfix.dkim.socket`     | `inet:localhost:8891`           | dkimpy-milter listen socket            |

### DKIM Keys

When `dkim.enable` is `true`, a 2048-bit RSA private key is generated at `/etc/dkimpy-milter/keys/default.key` if it does not exist. The corresponding public key must be added to the domain's DNS as a TXT record:

```
default._domainkey IN TXT "v=DKIM1; h=sha256; k=rsa; p=<public-key>"
```

## Tests

```sh
pytest -sv roles/ctlabs_postfix/tests
```

Validates template file existence and `--syntax-check` of the role via a localhost playbook.
