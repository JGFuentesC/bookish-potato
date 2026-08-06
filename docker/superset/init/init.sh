#!/bin/bash
set -e

echo "==> Superset init: upgrading metadata database"
superset db upgrade

echo "==> Superset init: creating admin user"
superset fab create-admin \
    --username "${SUPERSET_ADMIN_USER:-admin}" \
    --firstname Superset \
    --lastname Admin \
    --email admin@example.com \
    --password "${SUPERSET_ADMIN_PASSWORD:-admin}" \
    || true

echo "==> Superset init: loading default roles and permissions"
superset init

echo "==> Superset init: registering MySQL connections"
python /docker/superset-init/init_database.py

echo "==> Superset init: done"
