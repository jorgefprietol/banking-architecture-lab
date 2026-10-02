using Banking.Domain;
using Xunit;

namespace Banking.Tests;

public sealed class DomainTests
{
    private static Account AccountWith(long minor, string currency = "USD") => new(Guid.NewGuid(), new Money(minor, currency));

    [Fact]
    public void TransferConservesMoneyAndProducesBalancedEntries()
    {
        var source = AccountWith(500);
        var destination = AccountWith(100);
        var result = Transfer.Execute(source, destination, new Money(200, "USD"));
        Assert.Equal(600, source.Balance.Minor + destination.Balance.Minor);
        Assert.Equal(0, result.Debit.Delta + result.Credit.Delta);
        Assert.Equal(300, source.Balance.Minor);
        Assert.Equal(300, destination.Balance.Minor);
    }

    [Theory]
    [InlineData(-1)]
    [InlineData(9_000_000_000_001)]
    public void InvalidAmountsAreRejected(long amount) => Assert.Throws<DomainException>(() => new Money(amount, "USD"));

    [Fact]
    public void UnknownCurrencyIsRejected() => Assert.Throws<DomainException>(() => new Money(1, "XYZ"));

    [Fact]
    public void OverdraftDoesNotMutateEitherAccount()
    {
        var source = AccountWith(10);
        var destination = AccountWith(20);
        Assert.Equal("insufficient_funds", Assert.Throws<DomainException>(() => Transfer.Execute(source, destination, new Money(11, "USD"))).Code);
        Assert.Equal(10, source.Balance.Minor);
        Assert.Equal(20, destination.Balance.Minor);
        Assert.Equal(0, source.Version);
    }

    [Fact]
    public void CreditOverflowDoesNotDebitSource()
    {
        var source = AccountWith(20);
        var destination = AccountWith(Money.Maximum);
        Assert.Throws<DomainException>(() => Transfer.Execute(source, destination, new Money(1, "USD")));
        Assert.Equal(20, source.Balance.Minor);
    }

    [Fact]
    public void DifferentCurrenciesAreRejected() =>
        Assert.Throws<DomainException>(() => Transfer.Execute(AccountWith(20), AccountWith(0, "EUR"), new Money(1, "USD")));

    [Fact]
    public void SelfTransferIsRejected()
    {
        var account = AccountWith(10);
        Assert.Throws<DomainException>(() => Transfer.Execute(account, account, new Money(1, "USD")));
    }

    [Fact]
    public void ZeroTransferIsRejected() =>
        Assert.Throws<DomainException>(() => Transfer.Execute(AccountWith(20), AccountWith(0), new Money(0, "USD")));

    [Fact]
    public void ReplayReconstructsBalanceAndVersion()
    {
        var id = Guid.NewGuid();
        var replay = Account.Replay(id, "USD", [new(id, 1, 500, "USD"), new(id, 2, -75, "USD")]);
        Assert.Equal(425, replay.Balance.Minor);
        Assert.Equal(2, replay.Version);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(2)]
    public void ReplayRejectsVersionGaps(int version)
    {
        var id = Guid.NewGuid();
        Assert.Throws<DomainException>(() => Account.Replay(id, "USD", [new(id, version, 10, "USD")]));
    }

    [Fact]
    public void ReplayRejectsEventFromAnotherAccount()
    {
        Assert.Throws<DomainException>(() => Account.Replay(Guid.NewGuid(), "USD", [new(Guid.NewGuid(), 1, 10, "USD")]));
    }

    [Fact]
    public void GeneratedTransfersPreserveTotal()
    {
        var random = new Random(42);
        for (var i = 0; i < 1000; i++)
        {
            var amount = random.NextInt64(1, 1_000_000);
            var source = AccountWith(amount + random.NextInt64(0, 1_000_000));
            var destination = AccountWith(random.NextInt64(0, 1_000_000));
            var before = source.Balance.Minor + destination.Balance.Minor;
            Transfer.Execute(source, destination, new Money(amount, "USD"));
            Assert.Equal(before, source.Balance.Minor + destination.Balance.Minor);
        }
    }

    [Fact]
    public void RiskEvaluatesEveryPluginWithStableOrdering()
    {
        var engine = new RiskEngine([new VelocityRule(), new SanctionsRule(), new AmountRule()]);
        var findings = engine.Evaluate(new(1_000_001, 5, true));
        Assert.Equal(["amount", "sanctions", "velocity"], findings.Select(x => x.Rule));
        Assert.All(findings, x => Assert.True(x.Blocked));
    }

    [Fact]
    public void RiskAllowsBoundaryAmountAndVelocityBelowLimit()
    {
        var engine = new RiskEngine([new AmountRule(), new VelocityRule(), new SanctionsRule()]);
        Assert.All(engine.Evaluate(new(1_000_000, 4, false)), x => Assert.False(x.Blocked));
    }

    [Fact]
    public void DuplicatePluginsAreRejected() => Assert.Throws<DomainException>(() => new RiskEngine([new AmountRule(), new AmountRule()]));

    [Fact]
    public void NegativeSignalsAreRejected() => Assert.Throws<DomainException>(() => new RiskEngine([new AmountRule()]).Evaluate(new(-1, 0, false)));

    [Fact]
    public void ReconciliationClassifiesAllDifferences()
    {
        var result = Reconciliation.Compare([new("a", 1), new("b", 2), new("d", 1), new("d", 1)],
            [new("a", 3), new("c", 1), new("d", 1)]);
        Assert.Equal(["amount_mismatch", "missing_provider", "missing_internal", "duplicate"], result.Select(x => x.Kind));
    }

    [Fact]
    public void MatchedSettlementProducesNoDiscrepancies() =>
        Assert.Empty(Reconciliation.Compare([new("a", 10)], [new("a", 10)]));

    [Fact]
    public void ReservationRetryAndCancellationAreIdempotent()
    {
        var inventory = new Inventory(10);
        var id = Guid.NewGuid();
        inventory.Reserve(id, 3, 0);
        inventory.Reserve(id, 3, 0);
        Assert.Equal(7, inventory.Available);
        inventory.Cancel(id, 1);
        inventory.Cancel(id, 1);
        Assert.Equal(10, inventory.Available);
        Assert.Equal(2, inventory.Version);
    }

    [Fact]
    public void StaleReservationIsRejected()
    {
        var inventory = new Inventory(10);
        inventory.Reserve(Guid.NewGuid(), 3, 0);
        Assert.Throws<DomainException>(() => inventory.Reserve(Guid.NewGuid(), 3, 0));
        Assert.Equal(7, inventory.Available);
    }

    [Fact]
    public void OversellIsRejected() => Assert.Throws<DomainException>(() => new Inventory(2).Reserve(Guid.NewGuid(), 3, 0));

    [Fact]
    public void CancelledReservationCannotBeReused()
    {
        var inventory = new Inventory(10);
        var id = Guid.NewGuid();
        inventory.Reserve(id, 3, 0);
        inventory.Cancel(id, 1);
        Assert.Throws<DomainException>(() => inventory.Reserve(id, 3, 2));
    }

    private sealed class Identity(bool eligible) : IIdentityCheck { public bool Eligible(string reference) => eligible; }
    private sealed class Provisioner(bool fail = false, bool failRelease = false) : IAccountProvisioner
    {
        public int Reservations { get; private set; }
        public bool Released { get; private set; }
        public Guid Reserve(string reference) { Reservations++; return Guid.NewGuid(); }
        public void Activate(Guid id) { if (fail) throw new InvalidOperationException("provider_unavailable"); }
        public void Release(Guid id) { if (failRelease) throw new InvalidOperationException("compensation_pending"); Released = true; }
    }

    [Fact]
    public void KycRejectionDoesNotReserve()
    {
        var provisioner = new Provisioner();
        Assert.Equal(OnboardingState.Rejected, new OpenAccount(new Identity(false), provisioner).Execute("synthetic-1").State);
        Assert.Equal(0, provisioner.Reservations);
    }

    [Fact]
    public void ApprovedApplicantOpensAccount()
    {
        var result = new OpenAccount(new Identity(true), new Provisioner()).Execute("synthetic-1");
        Assert.Equal(OnboardingState.Opened, result.State);
        Assert.NotNull(result.AccountId);
    }

    [Fact]
    public void ActivationFailureCompensatesReservation()
    {
        var provisioner = new Provisioner(true);
        Assert.Equal(OnboardingState.Compensated, new OpenAccount(new Identity(true), provisioner).Execute("synthetic-1").State);
        Assert.True(provisioner.Released);
    }

    [Fact]
    public void CompensationFailureRemainsVisible() =>
        Assert.Throws<InvalidOperationException>(() => new OpenAccount(new Identity(true), new Provisioner(true, true)).Execute("synthetic-1"));

    [Fact]
    public void DomainHasNoFrameworkOrInfrastructureDependency()
    {
        var dependencies = typeof(Account).Assembly.GetReferencedAssemblies().Select(x => x.Name).ToArray();
        Assert.DoesNotContain(dependencies, x => x!.StartsWith("Npgsql", StringComparison.Ordinal) || x.StartsWith("Microsoft.AspNetCore", StringComparison.Ordinal));
    }
}
