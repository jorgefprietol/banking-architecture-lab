package dev.portfolio.banking.api;

import dev.portfolio.banking.application.Ledger;
import dev.portfolio.banking.application.Payments;
import dev.portfolio.banking.domain.Account;
import dev.portfolio.banking.domain.DomainException;
import dev.portfolio.banking.domain.Reconciliation;
import dev.portfolio.banking.domain.RiskEngine;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
public class LedgerController {
    private final Ledger ledger;
    private final Payments payments;
    private final RiskEngine risk;
    private final JdbcTemplate db;
    public LedgerController(Ledger ledger, Payments payments, RiskEngine risk, JdbcTemplate db) {
        this.ledger = ledger; this.payments = payments; this.risk = risk; this.db = db;
    }
    static boolean admin(Jwt jwt) {
        Map<String, Object> realm = jwt.getClaim("realm_access");
        return realm != null && ((Collection<?>)realm.getOrDefault("roles", List.of())).contains("admin");
    }
    @GetMapping("/health/live") public Map<String, String> live() { return Map.of("status", "UP"); }
    @GetMapping("/health/ready") public Map<String, String> ready() {
        db.queryForObject("SELECT version FROM schema_migrations WHERE version=1", Integer.class);
        return Map.of("status", "UP");
    }
    @PostMapping("/api/accounts") @ResponseStatus(HttpStatus.CREATED)
    public Ledger.AccountView open(@RequestBody Ledger.CreateAccount request) { return ledger.open(request); }
    @GetMapping("/api/accounts/{id}")
    public Ledger.AccountView read(@PathVariable UUID id, @AuthenticationPrincipal Jwt jwt) { return ledger.read(id, jwt.getSubject(), admin(jwt)); }
    @GetMapping("/api/accounts/{id}/events")
    public List<Account.Event> history(@PathVariable UUID id, @AuthenticationPrincipal Jwt jwt) { return ledger.history(id, jwt.getSubject(), admin(jwt)); }
    @PostMapping("/api/transfers") @ResponseStatus(HttpStatus.CREATED)
    public Ledger.Receipt transfer(@RequestBody Ledger.TransferCommand request, @RequestHeader(value="Idempotency-Key", required=false) String key, @AuthenticationPrincipal Jwt jwt) {
        UUID requestId;
        try { requestId = UUID.fromString(key); } catch (RuntimeException ex) { throw new DomainException("invalid_idempotency_key"); }
        return payments.execute(jwt.getSubject(), requestId, request);
    }
    @PostMapping("/api/risk/evaluate") public List<RiskEngine.Finding> risk(@RequestBody RiskEngine.Signal signal) { return risk.evaluate(signal); }
    public record ReconciliationRequest(List<Reconciliation.Row> internalRows, List<Reconciliation.Row> providerRows) {}
    @PostMapping("/api/reconciliation") public List<Reconciliation.Discrepancy> reconcile(@RequestBody ReconciliationRequest request) {
        return Reconciliation.compare(request.internalRows(), request.providerRows());
    }
}
