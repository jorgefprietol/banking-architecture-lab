package dev.portfolio.banking.domain;

public record Money(long minor, String currency) {
    public static final long MAXIMUM = 9_000_000_000_000L;
    public Money {
        if (minor < 0 || minor > MAXIMUM) throw new DomainException("invalid_amount");
        if (!"USD".equals(currency) && !"EUR".equals(currency)) throw new DomainException("invalid_currency");
    }
}
