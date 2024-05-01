#!/bin/bash

/opt/netbox/upgrade.sh                                                 && \
. /opt/netbox/venv/bin/activate                                        && \
export DJANGO_SUPERUSER_USERNAME="admin"                               && \
export DJANGO_SUPERUSER_PASSWORD='secret123!'                          && \
export DJANGO_SUPERUSER_EMAIL="admin@ctlabs.internal"                  && \
cd /opt/netbox/netbox && python3 ./manage.py createsuperuser --noinput &

exit 0