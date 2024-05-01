#!/bin/bash

function update() {
  /opt/netbox/upgrade.sh                                                 && \
  . /opt/netbox/venv/bin/activate                                        && \
  export DJANGO_SUPERUSER_USERNAME="admin"                               && \
  export DJANGO_SUPERUSER_PASSWORD='secret123!'                          && \
  export DJANGO_SUPERUSER_EMAIL="admin@ctlabs.internal"                  && \
  cd /opt/netbox/netbox && python3 ./manage.py createsuperuser --noinput &
  
  exit 0
}

function start() {
  . /opt/netbox/venv/bin/activate && \
  cd /opt/netbox/netbox           && \
  nohup python3 ./manage.py runserver 127.0.0.1:8080 --insecure &

  exit 0
}

case $1 in
  update)
    update
    ;;
  start)
    start
    ;;
esac