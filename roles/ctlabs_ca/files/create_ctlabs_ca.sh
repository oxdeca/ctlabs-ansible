#!/bin/bash

#
# GLOBALS
#
OPENSSL=/usr/bin/openssl
CONFIG="${1%.*}"
PASSPHRASE=passwd.${CONFIG}
SERIAL=$(/usr/bin/date +%s%N)

if [ -e "${CONFIG}.cnf" ]; then
	${OPENSSL} rand -base64 -out ${PASSPHRASE} 32
	${OPENSSL} req  -config ${CONFIG}.cnf -new -x509 -verbose -passout file:${PASSPHRASE} -days 365 -newkey rsa -set_serial ${SERIAL:0:12} -keyout ${CONFIG}.key -out ${CONFIG}.crt
fi
