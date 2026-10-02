BEGIN;
CREATE TABLE onboarding (
    actor text NOT NULL,
    request_id uuid NOT NULL,
    fingerprint text NOT NULL,
    state text NOT NULL CHECK(state IN ('Rejected','Opened')),
    account_id uuid REFERENCES accounts(id),
    PRIMARY KEY(actor,request_id)
);
GRANT SELECT, INSERT ON onboarding TO ledger_csharp, ledger_java;
INSERT INTO schema_migrations(version) VALUES (3);
COMMIT;
