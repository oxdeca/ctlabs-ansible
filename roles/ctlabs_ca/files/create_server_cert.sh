#!/bin/bash

#
# GLOBALS
#
OPENSSL=/usr/bin/openssl
CONFIG="${1%.*}"
PASSPHRASE=passwd.${CONFIG}
CA="${2}"
SERIAL=$(/usr/bin/date +%s%N)

if [ -e "${CONFIG}.cnf" ]; then
  ${OPENSSL} rand -base64 -out ${PASSPHRASE} 32
  ${OPENSSL} req -config ${CONFIG}.cnf -new -verbose -passout file:${PASSPHRASE} -days 365 -newkey rsa -keyout ${CONFIG}.key -out ${CONFIG}.csr
  ${OPENSSL} x509 -req -extfile ${CONFIG}.cnf -extensions v3_req -in ${CONFIG}.csr -days 365 -CA ${CA}.crt -passin file:passwd.${CA} -CAkey ${CA}.key -set_serial ${SERIAL:0:12} -out ${CONFIG}.crt
  ${OPENSSL} rsa  -in ${CONFIG}.key -passin file:${PASSPHRASE} > ${CONFIG}.prv
fi
