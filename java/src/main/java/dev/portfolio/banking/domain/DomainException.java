package dev.portfolio.banking.domain;

public final class DomainException extends RuntimeException {
    public DomainException(String code) { super(code); }
}
