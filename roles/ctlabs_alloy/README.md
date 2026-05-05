# Ansible Role `ctlabs_alloy`

## Ansible Tags

- `alloy`

## Ansible Local Facts

- `/etc/ansible/facts.d/ctlabs_alloy.fact`

```json
{
  "loki" : {
    "url" : "https://loki.ctlabs.internal:3100/loki/api/v1/push" 
  },
  "config" : {
    "email_archive" : true
  }
}
```


## Playbook

```yml
# -----------------------------------------------------------------------------
# ctlabs setup
# -----------------------------------------------------------------------------
- name  : ctlabs.playbooks.setup
  hosts : all:!rhosts
  tags  : setup
  tasks :
    - name: ctlabs.playbooks.ctlabs.setup.alloy.local_facts
      when: ansible_hostname in ['mail1', 'mail2']
      copy:
        dest: /etc/ansible/facts.d/ctlabs_alloy.fact
        content: |
          {
            "loki" : {
              "url" : "https://loki.ctlabs.internal:3100/loki/api/v1/push" 
            },
            "config" : {
              "email_archive" : true
            }
          }
```

```yml
# -----------------------------------------------------------------------------
# ctlabs_alloy
# -----------------------------------------------------------------------------
- name  : ctlabs.playbooks.ctlabs.alloy
  hosts : hosts
  tags  : alloy
  roles :
    - roles/ctlabs_alloy
```

