BEGIN;
ALTER TABLE account_events ADD COLUMN transfer_id uuid REFERENCES transfers(id) DEFERRABLE INITIALLY DEFERRED;
CREATE UNIQUE INDEX one_account_per_transfer ON account_events(account_id, transfer_id) WHERE transfer_id IS NOT NULL;
CREATE FUNCTION require_balanced_transfer() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE matched integer;
BEGIN
  SELECT count(*) INTO matched FROM account_events
    WHERE transfer_id=NEW.id AND currency=NEW.currency
      AND ((account_id=NEW.source_id AND delta=-NEW.amount_minor)
        OR (account_id=NEW.destination_id AND delta=NEW.amount_minor));
  IF NEW.source_id=NEW.destination_id OR matched<>2
     OR (SELECT count(*) FROM account_events WHERE transfer_id=NEW.id)<>2
     OR (SELECT sum(delta) FROM account_events WHERE transfer_id=NEW.id)<>0 THEN
    RAISE EXCEPTION 'unbalanced_transfer' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER balanced_transfer AFTER INSERT ON transfers
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION require_balanced_transfer();
INSERT INTO schema_migrations(version) VALUES(4);
COMMIT;
