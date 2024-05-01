#!/bin/bash

sudo -iu postgres psql <<EOF
CREATE DATABASE netbox;
CREATE USER netbox WITH PASSWORD 'secret123!';
ALTER DATABASE netbox OWNER TO netbox;
\connect netbox;
GRANT CREATE ON SCHEMA public TO netbox;
quit
EOF
exit
