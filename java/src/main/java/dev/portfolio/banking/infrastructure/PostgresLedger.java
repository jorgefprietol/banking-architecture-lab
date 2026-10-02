package dev.portfolio.banking.infrastructure;

import dev.portfolio.banking.application.Ledger;
import dev.portfolio.banking.domain.Account;
import dev.portfolio.banking.domain.DomainException;
import dev.portfolio.banking.domain.Money;
import dev.portfolio.banking.domain.Transfer;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;

public final class PostgresLedger implements Ledger {
    private final JdbcTemplate db;
    private final TransactionTemplate transaction;
    public PostgresLedger(JdbcTemplate db, TransactionTemplate transaction) { this.db = db; this.transaction = transaction; }
    public AccountView open(CreateAccount request) {
        var money = new Money(request.openingMinor(), request.currency());
        if (request.id() == null || request.id().equals(new UUID(0, 0)) || request.ownerId() == null || request.ownerId().isBlank())
            throw new DomainException("invalid_account");
        return transaction.execute(status -> {
            if (db.update("INSERT INTO accounts(id,owner_id,balance_minor,currency,version) VALUES(?,?,?,?,1) ON CONFLICT DO NOTHING",
                request.id(), request.ownerId(), money.minor(), money.currency()) != 1) throw new DomainException("account_exists");
            append(new Account.Event(request.id(), 1, money.minor(), money.currency()));
            return new AccountView(request.id(), request.ownerId(), money.minor(), money.currency(), 1);
        });
    }
    private void append(Account.Event event) {
        append(event, null);
    }
    private void append(Account.Event event, UUID transferId) {
        db.update("INSERT INTO account_events(event_id,account_id,version,delta,currency,transfer_id) VALUES(?,?,?,?,?,?)",
            UUID.randomUUID(), event.accountId(), event.version(), event.delta(), event.currency(), transferId);
    }
    public Receipt transfer(String actor, UUID key, TransferCommand request) {
        if (request.sourceId() == null || request.destinationId() == null) throw new DomainException("invalid_account");
        String fingerprint;
        try {
            fingerprint = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(
                (request.sourceId() + "|" + request.destinationId() + "|" + request.amountMinor() + "|" + request.currency()).getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
        return transaction.execute(status -> {
            db.query("SELECT pg_advisory_xact_lock(hashtextextended(?,0))", rs -> {}, actor + ":" + key);
            var previous = db.query("SELECT id,fingerprint,source_id,destination_id,amount_minor,currency FROM transfers WHERE actor=? AND request_key=?",
                (rs, row) -> {
                    if (!rs.getString("fingerprint").equals(fingerprint)) throw new DomainException("idempotency_conflict");
                    return new Receipt(rs.getObject("id", UUID.class), rs.getObject("source_id", UUID.class),
                        rs.getObject("destination_id", UUID.class), rs.getLong("amount_minor"), rs.getString("currency"));
                }, actor, key);
            if (!previous.isEmpty()) return previous.getFirst();
            var views = db.query("SELECT id,owner_id,balance_minor,currency,version FROM accounts WHERE id=? OR id=? ORDER BY id FOR UPDATE",
                (rs, row) -> new AccountView(rs.getObject("id", UUID.class), rs.getString("owner_id"), rs.getLong("balance_minor"), rs.getString("currency"), rs.getInt("version")),
                request.sourceId(), request.destinationId());
            var accounts = new HashMap<UUID, Account>();
            String owner = null;
            for (var view : views) {
                accounts.put(view.id(), new Account(view.id(), new Money(view.balanceMinor(), view.currency()), view.version()));
                if (view.id().equals(request.sourceId())) owner = view.ownerId();
            }
            if (!accounts.containsKey(request.sourceId()) || !accounts.containsKey(request.destinationId())) throw new DomainException("account_not_found");
            if (!actor.equals(owner)) throw new DomainException("forbidden");
            var result = Transfer.execute(accounts.get(request.sourceId()), accounts.get(request.destinationId()), new Money(request.amountMinor(), request.currency()));
            var receipt = new Receipt(UUID.randomUUID(), request.sourceId(), request.destinationId(), request.amountMinor(), request.currency());
            for (var event : List.of(result.debit(), result.credit())) {
                db.update("UPDATE accounts SET balance_minor=balance_minor+?,version=? WHERE id=?", event.delta(), event.version(), event.accountId());
                append(event, receipt.id());
            }
            db.update("INSERT INTO transfers(id,actor,request_key,fingerprint,source_id,destination_id,amount_minor,currency) VALUES(?,?,?,?,?,?,?,?)",
                receipt.id(), actor, key, fingerprint, receipt.sourceId(), receipt.destinationId(), receipt.amountMinor(), receipt.currency());
            var eventId = UUID.randomUUID();
            // Only UUIDs, a validated enum and an integer are interpolated in JSON, never user text.
            var payload = "{\"eventId\":\"" + eventId + "\",\"type\":\"TransferCompleted\",\"schemaVersion\":1,\"transferId\":\"" + receipt.id()
                + "\",\"sourceId\":\"" + receipt.sourceId() + "\",\"destinationId\":\"" + receipt.destinationId()
                + "\",\"amountMinor\":" + receipt.amountMinor() + ",\"currency\":\"" + receipt.currency() + "\"}";
            db.update("INSERT INTO outbox(event_id,aggregate_id,payload) VALUES(?,?,?::jsonb)", eventId, receipt.sourceId(), payload);
            return receipt;
        });
    }
    public AccountView read(UUID id, String actor, boolean admin) {
        var rows = db.query("SELECT owner_id,balance_minor,currency,version FROM accounts WHERE id=?",
            (rs, row) -> new AccountView(id, rs.getString("owner_id"), rs.getLong("balance_minor"), rs.getString("currency"), rs.getInt("version")), id);
        if (rows.isEmpty()) throw new DomainException("account_not_found");
        var view = rows.getFirst();
        if (!admin && !view.ownerId().equals(actor)) throw new DomainException("forbidden");
        return view;
    }
    public List<Account.Event> history(UUID id, String actor, boolean admin) {
        read(id, actor, admin);
        return db.query("SELECT version,delta,currency FROM account_events WHERE account_id=? ORDER BY version",
            (rs, row) -> new Account.Event(id, rs.getInt("version"), rs.getLong("delta"), rs.getString("currency")), id);
    }
}
