using Banking.Application;
using Banking.Domain;
using Xunit;

namespace Banking.Tests;

public sealed class EventProgrammingTests
{
    [Fact]
    public void NewSubscribersObserveTransferWithoutChangingItsRules()
    {
        var source = new Account(Guid.NewGuid(), new Money(100, "USD"));
        var destination = new Account(Guid.NewGuid(), new Money(0, "USD"));
        var dispatcher = new EventDispatcher();
        var balanceChanges = new List<long>();
        var observedVersions = new List<int>();
        dispatcher.Subscribe<AccountEvent>(entry => balanceChanges.Add(entry.Delta));
        dispatcher.Subscribe<AccountEvent>(entry => observedVersions.Add(entry.Version));
        var transfer = Transfer.Execute(source, destination, new Money(30, "USD"));
        dispatcher.Publish(transfer.Debit);
        dispatcher.Publish(transfer.Credit);
        Assert.Equal([-30L, 30L], balanceChanges);
        Assert.Equal([1, 1], observedVersions);
        Assert.Equal(100, source.Balance.Minor + destination.Balance.Minor);
    }

    [Fact]
    public void RestoredCancellationKeepsOriginalReservationIdentity()
    {
        var id = Guid.NewGuid();
        var restored = Inventory.Restore(7, 1, [new(id, 3, false)]);
        restored.Cancel(id, 1);
        restored.Cancel(id, 1);
        Assert.Equal(10, restored.Available);
        Assert.Equal(2, restored.Version);
    }
}
