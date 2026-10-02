package dev.portfolio.banking.domain;

public final class Transfer {
    private Transfer() {}
    public record Result(Account.Event debit, Account.Event credit) {}
    public static Result execute(Account source, Account destination, Money amount) {
        if (source.id().equals(destination.id())) throw new DomainException("same_account");
        if (amount.minor() == 0) throw new DomainException("invalid_amount");
        if (!source.balance().currency().equals(amount.currency()) || !destination.balance().currency().equals(amount.currency()))
            throw new DomainException("currency_mismatch");
        if (source.balance().minor() < amount.minor()) throw new DomainException("insufficient_funds");
        if (destination.balance().minor() > Money.MAXIMUM - amount.minor()) throw new DomainException("invalid_amount");
        return new Result(source.apply(-amount.minor()), destination.apply(amount.minor()));
    }
}
