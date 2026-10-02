package dev.portfolio.banking.infrastructure;

import dev.portfolio.banking.application.OnboardingStore;
import dev.portfolio.banking.domain.DomainException;
import dev.portfolio.banking.domain.Money;
import dev.portfolio.banking.domain.Onboarding;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.UUID;

public final class PostgresOnboarding implements OnboardingStore {
    private final JdbcTemplate db;
    private final TransactionTemplate tx;
    private final Onboarding.IdentityCheck identity;
    public PostgresOnboarding(JdbcTemplate db, TransactionTemplate tx, Onboarding.IdentityCheck identity) {
        this.db = db; this.tx = tx; this.identity = identity;
    }
    public View execute(String actor, UUID requestId, Request request) {
        if (requestId == null || requestId.equals(new UUID(0, 0)) || request.applicantReference() == null ||
            request.applicantReference().isBlank() || request.applicantReference().length() > 128) throw new DomainException("invalid_applicant");
        new Money(0, request.currency());
        String fingerprint;
        try { fingerprint = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(
            (request.applicantReference() + "|" + request.currency()).getBytes(StandardCharsets.UTF_8))); }
        catch (java.security.NoSuchAlgorithmException ex) { throw new IllegalStateException(ex); }
        return tx.execute(status -> {
            db.query("SELECT pg_advisory_xact_lock(hashtextextended(?,0))", rs -> {}, "onboarding:" + actor + ":" + requestId);
            var previous = db.query("SELECT state,account_id,fingerprint FROM onboarding WHERE actor=? AND request_id=?", (rs, row) -> {
                if (!fingerprint.equals(rs.getString("fingerprint"))) throw new DomainException("idempotency_conflict");
                return new View(rs.getString("state"), rs.getObject("account_id", UUID.class));
            }, actor, requestId);
            if (!previous.isEmpty()) return previous.getFirst();
            boolean eligible = identity.eligible(request.applicantReference());
            var accountId = eligible ? UUID.randomUUID() : null;
            if (eligible) {
                db.update("INSERT INTO accounts(id,owner_id,currency,balance_minor,version) VALUES(?,?,?,0,1)", accountId, actor, request.currency());
                db.update("INSERT INTO account_events(event_id,account_id,version,delta,currency) VALUES(?,?,1,0,?)", UUID.randomUUID(), accountId, request.currency());
            }
            var state = eligible ? "Opened" : "Rejected";
            db.update("INSERT INTO onboarding(actor,request_id,fingerprint,state,account_id) VALUES(?,?,?,?,?)", actor, requestId, fingerprint, state, accountId);
            return new View(state, accountId);
        });
    }
}
