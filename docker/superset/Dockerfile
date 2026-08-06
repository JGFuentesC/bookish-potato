FROM apache/superset:4.1.4

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config \
    && pip install --no-cache-dir mysqlclient==2.2.7 pymysql==1.1.1 \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

USER superset
