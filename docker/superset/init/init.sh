#!/bin/bash
set -e

echo "==> Superset init: upgrading metadata database"
superset db upgrade

echo "==> Superset init: creating admin user"
superset fab create-admin \
    --username "${SUPERSET_ADMIN_USER:?SUPERSET_ADMIN_USER obligatorio}" \
    --firstname Superset \
    --lastname Admin \
    --email admin@example.com \
    --password "${SUPERSET_ADMIN_PASSWORD:?SUPERSET_ADMIN_PASSWORD obligatorio}" \
    || true

echo "==> Superset init: loading default roles and permissions"
superset init

echo "==> Superset init: registering MySQL connections"
python /docker/superset-init/init_database.py

echo "==> Superset init: done"
