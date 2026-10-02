CREATE TABLE inbox (
    event_id uuid PRIMARY KEY,
    transfer_id uuid NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE schema_migrations(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
INSERT INTO schema_migrations(version) VALUES (1);
