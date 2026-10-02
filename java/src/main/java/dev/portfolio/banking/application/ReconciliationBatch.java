package dev.portfolio.banking.application;

import dev.portfolio.banking.domain.Reconciliation;
import java.util.List;

public final class ReconciliationBatch {
    public interface SettlementSource { List<Reconciliation.Row> read(); }
    private final SettlementSource ledger;
    private final SettlementSource provider;
    public ReconciliationBatch(SettlementSource ledger, SettlementSource provider) { this.ledger = ledger; this.provider = provider; }
    public List<Reconciliation.Discrepancy> execute() { return Reconciliation.compare(ledger.read(), provider.read()); }
}
