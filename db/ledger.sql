CREATE TABLE accounts (
    id uuid PRIMARY KEY,
    owner_id text NOT NULL,
    currency text NOT NULL CHECK (currency IN ('USD', 'EUR')),
    balance_minor bigint NOT NULL CHECK (balance_minor BETWEEN 0 AND 9000000000000),
    version integer NOT NULL CHECK (version > 0)
);
CREATE TABLE account_events (
    event_id uuid PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES accounts(id),
    version integer NOT NULL,
    delta bigint NOT NULL,
    currency text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (account_id, version)
);
CREATE TABLE transfers (
    id uuid PRIMARY KEY,
    actor text NOT NULL,
    request_key uuid NOT NULL,
    fingerprint text NOT NULL,
    source_id uuid NOT NULL REFERENCES accounts(id),
    destination_id uuid NOT NULL REFERENCES accounts(id),
    amount_minor bigint NOT NULL CHECK (amount_minor > 0),
    currency text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(actor, request_key)
);
CREATE TABLE outbox (
    event_id uuid PRIMARY KEY,
    aggregate_id uuid NOT NULL,
    payload jsonb NOT NULL,
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX pending_outbox ON outbox(created_at) WHERE published_at IS NULL;

CREATE TABLE products (
    id uuid PRIMARY KEY,
    stock integer NOT NULL CHECK(stock >= 0),
    version integer NOT NULL DEFAULT 0
);
CREATE TABLE reservations (
    id uuid PRIMARY KEY,
    product_id uuid NOT NULL REFERENCES products(id),
    quantity integer NOT NULL CHECK(quantity > 0),
    cancelled boolean NOT NULL DEFAULT false
);

-- v1 is an immutable initial migration. Future changes use new numbered files.
CREATE TABLE schema_migrations(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
INSERT INTO schema_migrations(version) VALUES (1);
