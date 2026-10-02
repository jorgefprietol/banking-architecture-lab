package dev.portfolio.banking.application;

import dev.portfolio.banking.domain.DomainException;
import dev.portfolio.banking.domain.Money;
import java.util.UUID;

public final class Payments {
    private final Ledger ledger;
    public Payments(Ledger ledger) { this.ledger = ledger; }
    public Ledger.Receipt execute(String actor, UUID key, Ledger.TransferCommand request) {
        if (key == null || key.equals(new UUID(0, 0))) throw new DomainException("invalid_idempotency_key");
        new Money(request.amountMinor(), request.currency());
        return ledger.transfer(actor, key, request);
    }
}
