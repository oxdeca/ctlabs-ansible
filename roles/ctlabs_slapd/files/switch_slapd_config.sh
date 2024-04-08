#!/bin/bash

LDAPDIR=/etc/openldap
USER=ldap
GROUP=ldap


if [ -d "${LDAPDIR}/slapd.d" ]; then
  echo "Switching from slapd-config to slapd.conf"
  systemctl stop slapd
  mv ${LDAPDIR}/slapd.d ${LDAPDIR}/slapd.d.$(date +%Y%m%d%H%M%S)
  systemctl start slapd
else
  echo "Switching from slapd.conf to slapd-config"
 mkdir ${LDAPDIR}/slapd.d
 slaptest -f ${LDAPDIR}/slapd.conf -F ${LDAPDIR}/slapd.d
 chown -R ${USER}:${GROUP} ${LDAPDIR}/slapd.d
 systemctl restart slapd
fi