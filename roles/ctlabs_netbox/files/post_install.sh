#!/bin/bash

/opt/netbox/upgrade.sh

. /opt/netbox/venv/bin/activate && cd /opt/netbox/netbox &&  DJANGO_SUPERUSER_USERNAME="admin" DJANGO_SUPERUSER_PASSWORD="secret123!" DJANGO_SUPERUSER_EMAIL="admin@ctlabs.internal" python3 ./manage.py createsuperuser --noinput

