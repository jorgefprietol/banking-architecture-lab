package dev.portfolio.banking.domain;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import java.util.List;
import java.util.Random;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;

class DomainTest {
    Account account(long minor) { return new Account(UUID.randomUUID(), new Money(minor, "USD"), 0); }
    @Test void transferConservesMoneyAndProducesBalancedEntries() {
        var source = account(500); var destination = account(100);
        var result = Transfer.execute(source, destination, new Money(200, "USD"));
        assertEquals(600, source.balance().minor() + destination.balance().minor());
        assertEquals(0, result.debit().delta() + result.credit().delta());
        assertEquals(300, source.balance().minor());
        assertEquals(300, destination.balance().minor());
    }
    @ParameterizedTest @ValueSource(longs = {-1, 9_000_000_000_001L})
    void invalidAmountsAreRejected(long minor) { assertThrows(DomainException.class, () -> new Money(minor, "USD")); }
    @Test void unknownCurrencyIsRejected() { assertThrows(DomainException.class, () -> new Money(1, "XYZ")); }
    @Test void overdraftDoesNotMutateEitherAccount() {
        var source = account(10); var destination = account(20);
        var error = assertThrows(DomainException.class, () -> Transfer.execute(source, destination, new Money(11, "USD")));
        assertEquals("insufficient_funds", error.getMessage());
        assertEquals(10, source.balance().minor()); assertEquals(20, destination.balance().minor()); assertEquals(0, source.version());
    }
    @Test void creditOverflowDoesNotDebitSource() {
        var source = account(20);
        assertThrows(DomainException.class, () -> Transfer.execute(source, account(Money.MAXIMUM), new Money(1, "USD")));
        assertEquals(20, source.balance().minor());
    }
    @Test void differentCurrenciesAreRejected() {
        assertThrows(DomainException.class, () -> Transfer.execute(account(20), new Account(UUID.randomUUID(), new Money(0, "EUR"), 0), new Money(1, "USD")));
    }
    @Test void selfTransferIsRejected() {
        var account = account(20); assertThrows(DomainException.class, () -> Transfer.execute(account, account, new Money(1, "USD")));
    }
    @Test void zeroTransferIsRejected() { assertThrows(DomainException.class, () -> Transfer.execute(account(20), account(0), new Money(0, "USD"))); }
    @Test void replayReconstructsBalanceAndVersion() {
        var id = UUID.randomUUID();
        var replay = Account.replay(id, "USD", List.of(new Account.Event(id, 1, 500, "USD"), new Account.Event(id, 2, -75, "USD")));
        assertEquals(425, replay.balance().minor()); assertEquals(2, replay.version());
    }
    @ParameterizedTest @ValueSource(ints = {0, 2})
    void replayRejectsVersionGaps(int version) {
        var id = UUID.randomUUID(); assertThrows(DomainException.class, () -> Account.replay(id, "USD", List.of(new Account.Event(id, version, 10, "USD"))));
    }
    @Test void replayRejectsEventFromAnotherAccount() {
        assertThrows(DomainException.class, () -> Account.replay(UUID.randomUUID(), "USD", List.of(new Account.Event(UUID.randomUUID(), 1, 10, "USD"))));
    }
    @Test void generatedTransfersPreserveTotal() {
        var random = new Random(42);
        for (int i = 0; i < 1000; i++) {
            var amount = random.nextLong(1, 1_000_000);
            var source = account(amount + random.nextLong(0, 1_000_000)); var destination = account(random.nextLong(0, 1_000_000));
            var before = source.balance().minor() + destination.balance().minor();
            Transfer.execute(source, destination, new Money(amount, "USD"));
            assertEquals(before, source.balance().minor() + destination.balance().minor());
        }
    }
    @Test void riskEvaluatesEveryPluginWithStableOrdering() {
        var engine = new RiskEngine(List.of(new RiskEngine.Velocity(), new RiskEngine.Sanctions(), new RiskEngine.Amount()));
        var result = engine.evaluate(new RiskEngine.Signal(1_000_001, 5, true));
        assertEquals(List.of("amount", "sanctions", "velocity"), result.stream().map(RiskEngine.Finding::rule).toList());
        assertTrue(result.stream().allMatch(RiskEngine.Finding::blocked));
    }
    @Test void riskAllowsBoundaryAmountAndVelocityBelowLimit() {
        var engine = new RiskEngine(List.of(new RiskEngine.Velocity(), new RiskEngine.Sanctions(), new RiskEngine.Amount()));
        assertTrue(engine.evaluate(new RiskEngine.Signal(1_000_000, 4, false)).stream().noneMatch(RiskEngine.Finding::blocked));
    }
    @Test void duplicatePluginsAreRejected() { assertThrows(DomainException.class, () -> new RiskEngine(List.of(new RiskEngine.Amount(), new RiskEngine.Amount()))); }
    @Test void negativeSignalsAreRejected() { assertThrows(DomainException.class, () -> new RiskEngine(List.of(new RiskEngine.Amount())).evaluate(new RiskEngine.Signal(-1, 0, false))); }
    @Test void reconciliationClassifiesAllDifferences() {
        var result = Reconciliation.compare(List.of(new Reconciliation.Row("a", 1), new Reconciliation.Row("b", 2), new Reconciliation.Row("d", 1), new Reconciliation.Row("d", 1)),
            List.of(new Reconciliation.Row("a", 3), new Reconciliation.Row("c", 1), new Reconciliation.Row("d", 1)));
        assertEquals(List.of("amount_mismatch", "missing_provider", "missing_internal", "duplicate"), result.stream().map(Reconciliation.Discrepancy::kind).toList());
    }
    @Test void matchedSettlementProducesNoDiscrepancies() { assertTrue(Reconciliation.compare(List.of(new Reconciliation.Row("a", 10)), List.of(new Reconciliation.Row("a", 10))).isEmpty()); }
    @Test void reservationRetryAndCancellationAreIdempotent() {
        var inventory = new Inventory(10); var id = UUID.randomUUID();
        inventory.reserve(id, 3, 0); inventory.reserve(id, 3, 0); assertEquals(7, inventory.available());
        inventory.cancel(id, 1); inventory.cancel(id, 1); assertEquals(10, inventory.available()); assertEquals(2, inventory.version());
    }
    @Test void staleReservationIsRejected() {
        var inventory = new Inventory(10); inventory.reserve(UUID.randomUUID(), 3, 0);
        assertThrows(DomainException.class, () -> inventory.reserve(UUID.randomUUID(), 3, 0)); assertEquals(7, inventory.available());
    }
    @Test void oversellIsRejected() { assertThrows(DomainException.class, () -> new Inventory(2).reserve(UUID.randomUUID(), 3, 0)); }
    @Test void cancelledReservationCannotBeReused() {
        var inventory = new Inventory(10); var id = UUID.randomUUID();
        inventory.reserve(id, 3, 0); inventory.cancel(id, 1);
        assertThrows(DomainException.class, () -> inventory.reserve(id, 3, 2));
    }
    static final class Provisioner implements Onboarding.AccountProvisioner {
        int reservations; boolean released; boolean fail; boolean failRelease;
        public UUID reserve(String reference) { reservations++; return UUID.randomUUID(); }
        public void activate(UUID id) { if (fail) throw new IllegalStateException("provider_unavailable"); }
        public void release(UUID id) { if (failRelease) throw new IllegalStateException("compensation_pending"); released = true; }
    }
    @Test void kycRejectionDoesNotReserve() {
        var provider = new Provisioner();
        assertEquals(Onboarding.State.Rejected, new Onboarding(ref -> false, provider).execute("synthetic-1").state()); assertEquals(0, provider.reservations);
    }
    @Test void approvedApplicantOpensAccount() {
        var result = new Onboarding(ref -> true, new Provisioner()).execute("synthetic-1");
        assertEquals(Onboarding.State.Opened, result.state()); assertNotNull(result.accountId());
    }
    @Test void activationFailureCompensatesReservation() {
        var provider = new Provisioner(); provider.fail = true;
        assertEquals(Onboarding.State.Compensated, new Onboarding(ref -> true, provider).execute("synthetic-1").state()); assertTrue(provider.released);
    }
    @Test void compensationFailureRemainsVisible() {
        var provider = new Provisioner(); provider.fail = true; provider.failRelease = true;
        assertThrows(IllegalStateException.class, () -> new Onboarding(ref -> true, provider).execute("synthetic-1"));
    }
}
