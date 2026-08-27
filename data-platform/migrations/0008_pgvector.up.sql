CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE oltp.semantic_embedding (
    entity_ref text NOT NULL,
    kind       text NOT NULL,
    embedding  vector(768)
);