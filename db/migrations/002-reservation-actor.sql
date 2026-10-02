BEGIN;
ALTER TABLE reservations ADD COLUMN actor text NOT NULL DEFAULT 'legacy';
INSERT INTO schema_migrations(version) VALUES (2);
COMMIT;
