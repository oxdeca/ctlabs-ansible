#!/bin/bash

# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_aide/templates/aide-update.sh.j2
# Description : wrapper to re-baseline the AIDE database (accept current state)
# ------------------------------------------------------------------------------
set -u

AIDE="{{ ctlabs_aide.defaults.bin[ctg_os_family] }}"
CONFIG="{{ ctlabs_aide_config_file }}"
DBDIR="{{ ctlabs_aide.defaults.config.dbdir }}"
DB="{{ ctlabs_aide.defaults.config.db }}"
DBNEW="{{ ctlabs_aide.defaults.config.db_new }}"
ID="aide-update"

"${AIDE}" --config="${CONFIG}" --update
RC=$?

case "${RC}" in
    0|5|6)
        if [ -f "${DBDIR}/${DBNEW}" ]; then
            mv -f "${DBDIR}/${DBNEW}" "${DBDIR}/${DB}"
            logger -t "${ID}" "AIDE database re-baselined at ${DBDIR}/${DB}"
        else
            logger -t "${ID}" --priority user.warning \
                "AIDE update completed (aide rc=${RC}) but no new database found - nothing to promote"
        fi
        RC=0
        ;;
    *)
        logger -t "${ID}" --priority user.err \
            "AIDE database update FAILED (aide rc=${RC}) - baseline unchanged"
        ;;
esac

exit "${RC}"
