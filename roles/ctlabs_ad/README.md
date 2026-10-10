# Ansible Role `ctlabs_ad`



## Ansible Tags

- `ctlabs_ad`
- `ctlabs_ad.precheck`
- `ctlabs_ad.package`
- `ctlabs_ad.config`
- `ctlabs_ad.service`

## Configuration

### CTLABS Facts

| CTLABS Fact                  | Description      |
|------------------------------|------------------|
| `ctg_facts.ctlabs_ad.domain` | AD domain name   |

### Environment Variables

| VAR                      | Description
|--------------------------|-----------------------------------------------------|
| `CTLABS_AD_DOMAIN`       | AD-Domain, default value is `ad.ctlabs.internal`    |
| `CTLABS_AD_DOMAIN_LEAVE` | once the Variable is defined the leave task is run. |


## Network Requirements

| PROTO | DST-IP | DST-PORT | DESC         |
|-------|--------|----------|--------------|
| TCP   | host   | `22`	    | ssh          |
| TCP   | host   | `3389`   | winrdp       |
| TCP   | host   | `5986`   | ntlm - https |


## Examples

```bash
sh# ansible-playbook -i ./inventories/hosts.ini ./playbooks/init.yml -tad -e CTLABS_AD_DOMAIN=dev.ad.ctlabs.internal -l win-vm01 
```

```bash
sh# ansible-playbook -i ./inventories/hosts.ini ./playbooks/init.yml -tad -e CTLABS_AD_DOMAIN_LEAVE=true -l win-vm01
```


# References

  | No.                         | URI                                              |
  |-----------------------------|--------------------------------------------------|
  | <div id="01">[01]</div>     | <>    |
