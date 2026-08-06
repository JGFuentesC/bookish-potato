#!/bin/bash
set -e

mysql=( mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" )

echo "==> Creando base OLAP y usuarios de mínimo privilegio"

"${mysql[@]}" <<-EOSQL
  CREATE DATABASE IF NOT EXISTS finanzas_olap CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

  CREATE USER IF NOT EXISTS 'etl'@'%' IDENTIFIED BY '${MYSQL_ETL_PASSWORD}';
  CREATE USER IF NOT EXISTS 'dashboards'@'%' IDENTIFIED BY '${MYSQL_DASHBOARDS_PASSWORD}';

  -- etl: gestiona los esquemas (DDL + carga) pero NO usuarios ni otros esquemas
  GRANT ALL PRIVILEGES ON finanzas.* TO 'etl'@'%';
  GRANT ALL PRIVILEGES ON finanzas_olap.* TO 'etl'@'%';

  -- dashboards: solo lectura para la capa BI
  GRANT SELECT ON finanzas.* TO 'dashboards'@'%';
  GRANT SELECT ON finanzas_olap.* TO 'dashboards'@'%';

  FLUSH PRIVILEGES;
EOSQL

echo "==> Usuarios 'etl' y 'dashboards' listos"
