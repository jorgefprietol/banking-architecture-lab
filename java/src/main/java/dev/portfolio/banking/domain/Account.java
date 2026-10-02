package dev.portfolio.banking.domain;

import java.util.UUID;

public final class Account {
    public record Event(UUID accountId, int version, long delta, String currency) {}
    private final UUID id;
    private Money balance;
    private int version;

    public Account(UUID id, Money balance, int version) {
        if (id == null || id.equals(new UUID(0, 0)) || version < 0) throw new DomainException("invalid_account");
        this.id = id;
        this.balance = balance;
        this.version = version;
    }
    public UUID id() { return id; }
    public Money balance() { return balance; }
    public int version() { return version; }
    public Event apply(long delta) {
        long next;
        try { next = Math.addExact(balance.minor(), delta); }
        catch (ArithmeticException e) { throw new DomainException("invalid_amount"); }
        if (next < 0) throw new DomainException("insufficient_funds");
        var money = new Money(next, balance.currency());
        int nextVersion = Math.incrementExact(version);
        balance = money;
        version = nextVersion;
        return new Event(id, version, delta, balance.currency());
    }
    public static Account replay(UUID id, String currency, Iterable<Event> history) {
        var account = new Account(id, new Money(0, currency), 0);
        for (var event : history) {
            if (!event.accountId().equals(id) || !event.currency().equals(currency) || event.version() != account.version + 1)
                throw new DomainException("invalid_history");
            account.apply(event.delta());
        }
        return account;
    }
}
