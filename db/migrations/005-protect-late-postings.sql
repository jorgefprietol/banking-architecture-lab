BEGIN;
CREATE FUNCTION validate_transfer_postings(transfer_key uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE movement transfers%ROWTYPE;
DECLARE matched integer;
BEGIN
  SELECT * INTO movement FROM transfers WHERE id=transfer_key;
  IF NOT FOUND THEN RETURN; END IF;
  SELECT count(*) INTO matched FROM account_events
    WHERE transfer_id=movement.id AND currency=movement.currency
      AND ((account_id=movement.source_id AND delta=-movement.amount_minor)
        OR (account_id=movement.destination_id AND delta=movement.amount_minor));
  IF movement.source_id=movement.destination_id OR matched<>2
     OR (SELECT count(*) FROM account_events WHERE transfer_id=movement.id)<>2
     OR (SELECT sum(delta) FROM account_events WHERE transfer_id=movement.id)<>0 THEN
    RAISE EXCEPTION 'unbalanced_transfer' USING ERRCODE='23514';
  END IF;
END $$;
CREATE OR REPLACE FUNCTION require_balanced_transfer() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM validate_transfer_postings(NEW.id);
  RETURN NEW;
END $$;
CREATE FUNCTION require_balanced_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.transfer_id IS NOT NULL THEN
    PERFORM validate_transfer_postings(NEW.transfer_id);
  END IF;
  RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER balanced_event AFTER INSERT ON account_events
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION require_balanced_event();
INSERT INTO schema_migrations(version) VALUES(5);
COMMIT;
