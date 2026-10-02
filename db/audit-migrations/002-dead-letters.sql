BEGIN;
CREATE TABLE dead_letters (
    id uuid PRIMARY KEY,
    source_topic text NOT NULL,
    source_partition integer NOT NULL CHECK (source_partition >= 0),
    source_offset bigint NOT NULL CHECK (source_offset >= 0),
    raw_payload text,
    error_code text NOT NULL,
    payload jsonb NOT NULL,
    rejected_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    UNIQUE(source_topic, source_partition, source_offset)
);
CREATE INDEX dead_letters_pending ON dead_letters(rejected_at) WHERE published_at IS NULL;
GRANT SELECT, INSERT ON dead_letters TO audit_csharp, audit_java;
GRANT UPDATE(published_at) ON dead_letters TO audit_csharp, audit_java;
INSERT INTO schema_migrations(version) VALUES(2);
COMMIT;
