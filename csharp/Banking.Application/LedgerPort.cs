using Banking.Domain;

namespace Banking.Application;

public sealed record CreateAccount(Guid Id, string OwnerId, long OpeningMinor, string Currency);
public sealed record TransferCommand(Guid SourceId, Guid DestinationId, long AmountMinor, string Currency);
public sealed record Receipt(Guid Id, Guid SourceId, Guid DestinationId, long AmountMinor, string Currency);
public sealed record AccountView(Guid Id, string OwnerId, long BalanceMinor, string Currency, int Version);
public interface ILedger
{
    Task<AccountView> Open(CreateAccount request, CancellationToken ct);
    Task<Receipt> Transfer(string actor, Guid key, TransferCommand request, CancellationToken ct);
    Task<AccountView> Read(Guid id, string actor, bool admin, CancellationToken ct);
    Task<IReadOnlyList<AccountEvent>> History(Guid id, string actor, bool admin, CancellationToken ct);
}

public sealed class Payments(ILedger ledger)
{
    public Task<Receipt> Execute(string actor, Guid key, TransferCommand request, CancellationToken ct)
    {
        if (key == Guid.Empty) throw new DomainException("invalid_idempotency_key");
        _ = new Money(request.AmountMinor, request.Currency);
        return ledger.Transfer(actor, key, request, ct);
    }
}
