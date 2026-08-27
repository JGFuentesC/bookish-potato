CREATE TABLE oltp.ingestion_run (
    run_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      timestamptz NOT NULL,
    finished_at     timestamptz,
    status          text NOT NULL,
    scope           text NOT NULL,
    files_processed integer NOT NULL DEFAULT 0,
    rows_written    integer NOT NULL DEFAULT 0,
    error_summary   text
);

CREATE TABLE oltp.ingestion_file (
    run_id       uuid NOT NULL REFERENCES oltp.ingestion_run (run_id) ON DELETE RESTRICT,
    source_path  text NOT NULL,
    file_sha256  text NOT NULL,
    entity       text NOT NULL,
    rows         integer NOT NULL DEFAULT 0,
    status       text NOT NULL
);