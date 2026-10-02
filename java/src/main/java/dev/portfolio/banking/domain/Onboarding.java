package dev.portfolio.banking.domain;

import java.util.UUID;

public final class Onboarding {
    public enum State { Submitted, Rejected, Reserved, Opened, Compensated }
    public interface IdentityCheck { boolean eligible(String reference); }
    public interface AccountProvisioner { UUID reserve(String reference); void activate(UUID reservation); void release(UUID reservation); }
    public record Result(State state, UUID accountId) {}
    private final IdentityCheck identity;
    private final AccountProvisioner provisioner;
    public Onboarding(IdentityCheck identity, AccountProvisioner provisioner) {
        this.identity = identity;
        this.provisioner = provisioner;
    }
    public Result execute(String reference) {
        if (reference == null || reference.isBlank()) throw new DomainException("invalid_applicant");
        if (!identity.eligible(reference)) return new Result(State.Rejected, null);
        var reservation = provisioner.reserve(reference);
        try {
            provisioner.activate(reservation);
            return new Result(State.Opened, reservation);
        } catch (RuntimeException e) {
            provisioner.release(reservation);
            return new Result(State.Compensated, null);
        }
    }
}
