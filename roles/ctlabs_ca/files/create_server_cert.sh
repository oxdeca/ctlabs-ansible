#!/bin/bash

#
# GLOBALS
#
OPENSSL=/usr/bin/openssl
CONFIG="${1%.*}"
PASSPHRASE=passwd.${CONFIG}

if [ -e "${CONFIG}.cnf" ]; then
  ${OPENSSL} rand -base64 -out ${PASSPHRASE} 32
  ${OPENSSL} req -config ${CONFIG}.cnf -new -x509 -verbose -passout file:${PASSPHRASE} -days 365 -newkey rsa -keyout ${CONFIG}.key -out ${CONFIG}.csr
  ${OPENSSL} x509 -in ${CONFIG}.csr -days 365 -CA ca-test.crt -passin file:passwd.ca-test -CAkey ca-test.key -set_serial 01 -out ${CONFIG}.crt
  ${OPENSSL} rsa  -in ${CONFIG}.key -passin file:${PASSPHRASE} > ${CONFIG}.prv
fi
