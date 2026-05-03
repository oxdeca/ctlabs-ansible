# Ansible Role `ctlabs_atlantis`

## Ansible Tags

- `atlantis`

## Ansible Local Facts

- `ctlabs_gitea_atlantis_token`

## Playbook

```yml
# -----------------------------------------------------------------------------
# ctlabs_atlantis
# -----------------------------------------------------------------------------
- name  : ctlabs.playbooks.ctlabs.atlantis
  hosts : [ats1,ats2]
  tags  : atlantis
  roles :
    - roles/ctlabs_atlantis
```
