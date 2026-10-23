#!/bin/bash

#
# GLOBALS
#
OPENSSL=/usr/bin/openssl
CONFIG="${1%.*}"
PASSPHRASE=passwd.${CONFIG}
SERIAL=$(/usr/bin/date +%s%N)

if [ -e "${CONFIG}.cnf" ]; then
	# the ca is created once - an existing ca (crt + key) is never
	# regenerated, otherwise a host that lost its copy of the ca would
	# rotate the ca of the whole lab.
	if [ ! -e "${CONFIG}.crt" ] || [ ! -e "${CONFIG}.key" ]; then
		${OPENSSL} rand -base64 -out ${PASSPHRASE} 32
		${OPENSSL} req  -config ${CONFIG}.cnf -new -x509 -verbose -passout file:${PASSPHRASE} -days 365 -newkey rsa -set_serial ${SERIAL:0:12} -keyout ${CONFIG}.key -out ${CONFIG}.crt
	fi
fi
