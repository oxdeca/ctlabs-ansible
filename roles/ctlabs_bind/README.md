# Ansible Role `ctlabs_bind`

## Ansible Tags

- `bind`

## Zones

- master
- slave
- forward
- ddns

zones are configured via ansible local facts, e.g. 

___ns1: /etc/ansible/facts.d/ctlabs_bind.fact___

```json
{
  "type"   : "master",
  "zones"  : [
    { "name" : "ctlabs.internal" }, 
    { "name" : "svc.ctlabs.internal", "ddns" : { "allow" : [ "127.0.0.1" ] } },
    { "name" : "ad.ctlabs.internal", "type" : "forward", "forwarders" : [ "192.168.10.14" ] }
  ],
  "slaves" : [ "192.168.20.11" ]
}
```

## Zone Configuration

Zones are configures with the prefix `zone_`. The dots in the domain name will be replaced with an underscore. E.g. the zone for the domain `ctlabs.internal` would be `zone_ctlabs_internal` and records are under it.

```yml
zone_ctlabs_internal:
  - type  : COMMENT
    value : define name server for the domain

  - name  : '@'
    type  : NS
    value : ns1.ctlabs.internal.

  - name  : '@'
    type  : NS
    value : ns2.ctlabs.internal.

  - type  : COMMENT
    value : define mail exchangers for the domain

  - name  : '@'
    type  : MX
    value : 10 mail1.ctlabs.internal.

  - name  : '@'
    type  : MX
    value : 20 mail2.ctlabs.internal.

  - type  : COMMENT
    value : name server need A-records

# -----------------------------------------------------------------------------
# name server
# -----------------------------------------------------------------------------
  # the default record type is an 'A' record (can be left off)
  - name  : ns1
    value : 192.168.10.11

  - name  : ns2
    type  : A              # we can add the A type as well
    value : 192.168.20.11

# -----------------------------------------------------------------------------
# mail server
# -----------------------------------------------------------------------------
  - type  : COMMENT
    value : mail server need A-records

  - type  : mail1
    value : 192.168.10.15

  - type  : mail2
    value : 192.168.20.15
```

The above yaml file would be rendered as:

```r
; /var/named/data/ctlabs.internal/zone.db

$ORIGIN ctlabs.internal.
$TTL    3600

ctlabs.internal.   IN    SOA     ns1.ctlabs.internal. root.ctlabs.internal. (
                                  1761619985 ; serial
                                  3600       ; refresh
                                  600        ; retry
                                  86400      ; expire
                                  600        ; negative cache TTL
);


; define name server for the domain
@                                 IN  NS     ns1.ctlabs.internal.
@                                 IN  NS     ns2.ctlabs.internal.

; define mail exchangers for the domain
@                                 IN  MX     10 mail1.ctlabs.internal.
@                                 IN  MX     20 mail2.ctlabs.internal.

; name server need A-records
ns1                               IN  A      192.168.10.11
ns2                               IN  A      192.168.20.11

; mail server need A-records
mail1                             IN  A      192.168.10.15
mail2                             IN  A      192.168.20.15
```


## Record types

___A record___

```yml
zone_ctlabs_internal:
  - name  : www
    value : 192.168.30.13
```

___CNAME record___

```yml
zone_ctlab_internal:
  - name  : www1
    type  : CNAME
    value : www.ctlabs.internal.
```

___NS record___

```yml
zone_ctlabs_internal:
  - name  : '@'
    type  : NS
    value : ns1.ctlabs.internal.
```

___MX record___

```yml
zone_ctlabs_internal:
  - name  : '@'
    type  : MX
    value : mail1.ctlabs.internal.
```

___TXT record___

```yml
zone_ctlabs_internal:
  - name  : some_text
    type  : TXT
    value : cn=wer,ou=user,dc=me,dc=internal
```

___SRV record___

```yml
zone_ctlabs_internal:
  - name  : _ldap._tcp
    type  : SRV
    value : 10 50 389 dc1
```

___COMMENT___

```yml
zone_ctlabs_internal:
  - type  : COMMENT
    value : this is a comment in the zone file
```

