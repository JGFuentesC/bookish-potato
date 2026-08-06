CREATE DATABASE IF NOT EXISTS finanzas CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE finanzas;

CREATE TABLE IF NOT EXISTS lista (
  id     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  codigo VARCHAR(10)  NOT NULL,
  nombre VARCHAR(60)  NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_lista_codigo (codigo)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ticker (
  id        INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  simbolo   VARCHAR(20)   NOT NULL,
  nombre    VARCHAR(255)  NULL,
  sector    VARCHAR(80)   NULL,
  subsector VARCHAR(120)  NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_ticker_simbolo (simbolo)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ticker_lista (
  ticker_id INT UNSIGNED NOT NULL,
  lista_id  INT UNSIGNED NOT NULL,
  PRIMARY KEY (ticker_id, lista_id),
  KEY idx_tl_lista (lista_id),
  CONSTRAINT fk_tl_ticker FOREIGN KEY (ticker_id) REFERENCES ticker (id) ON DELETE CASCADE,
  CONSTRAINT fk_tl_lista  FOREIGN KEY (lista_id)  REFERENCES lista  (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS precio (
  ticker_id INT UNSIGNED    NOT NULL,
  fecha     DATE            NOT NULL,
  open      DECIMAL(18,6)   NULL,
  high      DECIMAL(18,6)   NULL,
  low       DECIMAL(18,6)   NULL,
  close     DECIMAL(18,6)   NULL,
  adj_close DECIMAL(18,6)   NULL,
  volumen   BIGINT UNSIGNED NULL,
  PRIMARY KEY (ticker_id, fecha),
  KEY idx_precio_fecha (fecha),
  CONSTRAINT fk_precio_ticker FOREIGN KEY (ticker_id) REFERENCES ticker (id) ON DELETE CASCADE
) ENGINE=InnoDB;
