CREATE DATABASE IF NOT EXISTS finanzas_olap CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE finanzas_olap;

-- ============================================================
-- DIMENSIONES (normalizadas en niveles: snowflake)
-- ============================================================

CREATE TABLE IF NOT EXISTS dim_anio (
  anio_id SMALLINT UNSIGNED NOT NULL PRIMARY KEY,
  anio    SMALLINT UNSIGNED NOT NULL UNIQUE,
  decada  SMALLINT UNSIGNED NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_mes (
  mes_id     INT UNSIGNED NOT NULL PRIMARY KEY,  -- anio*100 + mes
  mes_num    TINYINT UNSIGNED NOT NULL,
  mes_nombre VARCHAR(10)  NOT NULL,
  anio_id    SMALLINT UNSIGNED NOT NULL,
  CONSTRAINT fk_mes_anio FOREIGN KEY (anio_id) REFERENCES dim_anio (anio_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_fecha (
  fecha_id         INT UNSIGNED NOT NULL PRIMARY KEY,  -- YYYYMMDD
  fecha            DATE         NOT NULL UNIQUE,
  dia_num          TINYINT UNSIGNED NOT NULL,
  dia_semana       TINYINT UNSIGNED NOT NULL,          -- 1=Lun..7=Dom
  dia_semana_nombre VARCHAR(9) NOT NULL,
  semana_iso       VARCHAR(7)  NOT NULL,
  es_fin_semana    TINYINT(1)  NOT NULL,
  es_ultimo_dia_mes TINYINT(1) NOT NULL,
  mes_id           INT UNSIGNED NOT NULL,
  CONSTRAINT fk_fecha_mes FOREIGN KEY (mes_id) REFERENCES dim_mes (mes_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_sector (
  sector_id     SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  sector_nombre VARCHAR(80) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_subsector (
  subsector_id    INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  subsector_nombre VARCHAR(120) NOT NULL UNIQUE,
  sector_id       SMALLINT UNSIGNED NOT NULL,
  CONSTRAINT fk_subsector_sector FOREIGN KEY (sector_id) REFERENCES dim_sector (sector_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_empresa (
  empresa_id   INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  simbolo      VARCHAR(20) NOT NULL UNIQUE,
  nombre       VARCHAR(255) NULL,
  subsector_id INT UNSIGNED NOT NULL,
  CONSTRAINT fk_empresa_subsector FOREIGN KEY (subsector_id) REFERENCES dim_subsector (subsector_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_lista (
  lista_id INT UNSIGNED NOT NULL PRIMARY KEY,
  codigo   VARCHAR(10)  NOT NULL UNIQUE,
  nombre   VARCHAR(60)  NOT NULL
) ENGINE=InnoDB;

-- ============================================================
-- HECHOS
-- ============================================================

CREATE TABLE IF NOT EXISTS fact_precio_diario (
  empresa_id       INT UNSIGNED   NOT NULL,
  fecha_id         INT UNSIGNED   NOT NULL,
  open             DECIMAL(18,6)  NULL,
  high             DECIMAL(18,6)  NULL,
  low              DECIMAL(18,6)  NULL,
  close            DECIMAL(18,6)  NULL,
  adj_close        DECIMAL(18,6)  NULL,
  volumen          BIGINT UNSIGNED NULL,
  retorno_diario   DECIMAL(18,8)  NULL,
  retorno_log      DECIMAL(18,8)  NULL,
  retorno_ajustado DECIMAL(18,8)  NULL,
  rango            DECIMAL(18,6)  NULL,
  volumen_dolares  DECIMAL(24,2)  NULL,
  PRIMARY KEY (empresa_id, fecha_id),
  KEY idx_fd_fecha (fecha_id),
  CONSTRAINT fk_fd_empresa FOREIGN KEY (empresa_id) REFERENCES dim_empresa (empresa_id),
  CONSTRAINT fk_fd_fecha   FOREIGN KEY (fecha_id)   REFERENCES dim_fecha  (fecha_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS fact_precio_mensual (
  empresa_id         INT UNSIGNED NOT NULL,
  mes_id             INT UNSIGNED NOT NULL,
  open_primero       DECIMAL(18,6) NULL,
  close_ultimo       DECIMAL(18,6) NULL,
  high_max           DECIMAL(18,6) NULL,
  low_min            DECIMAL(18,6) NULL,
  volumen_total      BIGINT UNSIGNED NULL,
  retorno_mensual    DECIMAL(18,8) NULL,
  volatilidad_mensual DECIMAL(18,8) NULL,
  n_dias             INT UNSIGNED NOT NULL,
  PRIMARY KEY (empresa_id, mes_id),
  KEY idx_fm_mes (mes_id),
  CONSTRAINT fk_fm_empresa FOREIGN KEY (empresa_id) REFERENCES dim_empresa (empresa_id),
  CONSTRAINT fk_fm_mes     FOREIGN KEY (mes_id)     REFERENCES dim_mes     (mes_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS hecho_membresia (
  empresa_id INT UNSIGNED NOT NULL,
  lista_id   INT UNSIGNED NOT NULL,
  PRIMARY KEY (empresa_id, lista_id),
  KEY idx_hm_lista (lista_id),
  CONSTRAINT fk_hm_empresa FOREIGN KEY (empresa_id) REFERENCES dim_empresa (empresa_id),
  CONSTRAINT fk_hm_lista   FOREIGN KEY (lista_id)   REFERENCES dim_lista   (lista_id)
) ENGINE=InnoDB;

-- ============================================================
-- VISTAS DENORMALIZADAS (star) para dashboards / datasets
-- ============================================================

CREATE OR REPLACE VIEW vw_empresa AS
SELECT
  e.empresa_id,
  e.simbolo,
  e.nombre,
  ss.subsector_nombre,
  s.sector_nombre
FROM dim_empresa e
JOIN dim_subsector ss ON ss.subsector_id = e.subsector_id
JOIN dim_sector s     ON s.sector_id     = ss.sector_id;

CREATE OR REPLACE VIEW vw_membresia AS
SELECT
  hm.empresa_id,
  e.simbolo,
  l.lista_id,
  l.codigo AS lista_codigo,
  l.nombre AS lista_nombre
FROM hecho_membresia hm
JOIN dim_empresa e ON e.empresa_id = hm.empresa_id
JOIN dim_lista   l ON l.lista_id   = hm.lista_id;

CREATE OR REPLACE VIEW vw_diario AS
SELECT
  d.empresa_id,
  d.fecha_id,
  df.fecha,
  m.anio_id,
  m.mes_num,
  m.mes_nombre,
  df.dia_semana,
  df.dia_semana_nombre,
  df.es_fin_semana,
  e.simbolo,
  e.nombre,
  s.sector_nombre,
  ss.subsector_nombre,
  d.open,
  d.high,
  d.low,
  d.close,
  d.adj_close,
  d.volumen,
  d.retorno_diario,
  d.retorno_log,
  d.retorno_ajustado,
  d.rango,
  d.volumen_dolares,
  (hm1.lista_id IS NOT NULL) AS es_sp500,
  (hm2.lista_id IS NOT NULL) AS es_nasdaq,
  (hm3.lista_id IS NOT NULL) AS es_amex
FROM fact_precio_diario d
JOIN dim_empresa    e  ON e.empresa_id = d.empresa_id
JOIN dim_subsector  ss ON ss.subsector_id = e.subsector_id
JOIN dim_sector     s  ON s.sector_id = ss.sector_id
JOIN dim_fecha      df ON df.fecha_id = d.fecha_id
JOIN dim_mes        m  ON m.mes_id = df.mes_id
LEFT JOIN hecho_membresia hm1 ON hm1.empresa_id = d.empresa_id AND hm1.lista_id = 1
LEFT JOIN hecho_membresia hm2 ON hm2.empresa_id = d.empresa_id AND hm2.lista_id = 2
LEFT JOIN hecho_membresia hm3 ON hm3.empresa_id = d.empresa_id AND hm3.lista_id = 3;

CREATE OR REPLACE VIEW vw_mensual AS
SELECT
  f.empresa_id,
  f.mes_id,
  STR_TO_DATE(CONCAT(f.mes_id, '01'), '%Y%m%d') AS fecha_mes,
  m.anio_id,
  m.mes_num,
  m.mes_nombre,
  e.simbolo,
  e.nombre,
  s.sector_nombre,
  ss.subsector_nombre,
  f.open_primero,
  f.close_ultimo,
  f.high_max,
  f.low_min,
  f.volumen_total,
  f.retorno_mensual,
  f.volatilidad_mensual,
  f.n_dias,
  (hm1.lista_id IS NOT NULL) AS es_sp500,
  (hm2.lista_id IS NOT NULL) AS es_nasdaq,
  (hm3.lista_id IS NOT NULL) AS es_amex
FROM fact_precio_mensual f
JOIN dim_mes        m  ON m.mes_id = f.mes_id
JOIN dim_empresa    e  ON e.empresa_id = f.empresa_id
JOIN dim_subsector  ss ON ss.subsector_id = e.subsector_id
JOIN dim_sector     s  ON s.sector_id = ss.sector_id
LEFT JOIN hecho_membresia hm1 ON hm1.empresa_id = f.empresa_id AND hm1.lista_id = 1
LEFT JOIN hecho_membresia hm2 ON hm2.empresa_id = f.empresa_id AND hm2.lista_id = 2
LEFT JOIN hecho_membresia hm3 ON hm3.empresa_id = f.empresa_id AND hm3.lista_id = 3;
