#!/bin/bash

#
# CMDS
#
CAT=/usr/bin/cat
DATE=/usr/bin/date
INSTALL=/usr/bin/install
CHOWN=/usr/bin/chown
CHMOD=/usr/bin/chmod
GREP=/usr/bin/egrep
HOSTNAME=/usr/bin/hostname

#
# GLOBALS
#
HOST=$( ${HOSTNAME} --fqdn )
BASEDIR=/var/email_archive/${HOST}
YEAR=$( ${DATE} +%Y )
MONTH=$( ${DATE} +%m )
DAY=$( ${DATE} +%d )
RCPT=$( echo ${1} | ${GREP} "[a-z0-9_.!#$%&*+]+@[a-z0-9_.-]+" )
FILE=${BASEDIR}/$( ${DATE} +%Y/%m/%d )/${RCPT}

if [ -n "${RCPT}" ]; then
  if [ -f "${FILE}" ]; then
    ${CAT} -  >> ${FILE}
  else
    ${INSTALL} -D -m 0640 -o mail -g splunk <( ${CAT} - ) "${FILE}"

    ${CHOWN} mail.splunk ${BASEDIR}/${YEAR}
    ${CHOWN} mail.splunk ${BASEDIR}/${YEAR}/${MONTH}
    ${CHOWN} mail.splunk ${BASEDIR}/${YEAR}/${MONTH}/${DAY}

    ${CHMOD} 0750 ${BASEDIR}/${YEAR}
    ${CHMOD} 0750 ${BASEDIR}/${YEAR}/${MONTH}
    ${CHMOD} 0750 ${BASEDIR}/${YEAR}/${MONTH}/${DAY}
  fi

fi

exit 0
