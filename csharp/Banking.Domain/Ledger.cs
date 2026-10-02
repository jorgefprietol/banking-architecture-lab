namespace Banking.Domain;

public sealed class DomainException(string code) : Exception(code)
{
    public string Code { get; } = code;
}

public sealed record Money
{
    // The contract stays within the exact integer range of common JSON clients.
    public const long Maximum = 9_000_000_000_000;
    public long Minor { get; }
    public string Currency { get; }

    public Money(long minor, string currency)
    {
        if (minor is < 0 or > Maximum) throw new DomainException("invalid_amount");
        if (currency is not ("USD" or "EUR")) throw new DomainException("invalid_currency");
        Minor = minor;
        Currency = currency;
    }
}

public sealed record AccountEvent(Guid AccountId, int Version, long Delta, string Currency);

public sealed class Account
{
    public Guid Id { get; }
    public Money Balance { get; private set; }
    public int Version { get; private set; }

    public Account(Guid id, Money balance, int version = 0)
    {
        if (id == Guid.Empty || version < 0) throw new DomainException("invalid_account");
        Id = id;
        Balance = balance;
        Version = version;
    }

    public AccountEvent Apply(long delta)
    {
        long next;
        try { next = checked(Balance.Minor + delta); }
        catch (OverflowException) { throw new DomainException("invalid_amount"); }
        if (next < 0) throw new DomainException("insufficient_funds");
        var money = new Money(next, Balance.Currency);
        var nextVersion = checked(Version + 1);
        Balance = money;
        Version = nextVersion;
        return new AccountEvent(Id, Version, delta, Balance.Currency);
    }

    public static Account Replay(Guid id, string currency, IEnumerable<AccountEvent> history)
    {
        var account = new Account(id, new Money(0, currency));
        foreach (var entry in history)
        {
            if (entry.AccountId != id || entry.Currency != currency || entry.Version != account.Version + 1)
                throw new DomainException("invalid_history");
            account.Apply(entry.Delta);
        }
        return account;
    }
}

public sealed record TransferResult(AccountEvent Debit, AccountEvent Credit);

public static class Transfer
{
    public static TransferResult Execute(Account source, Account destination, Money amount)
    {
        if (source.Id == destination.Id) throw new DomainException("same_account");
        if (amount.Minor == 0) throw new DomainException("invalid_amount");
        if (source.Balance.Currency != amount.Currency || destination.Balance.Currency != amount.Currency)
            throw new DomainException("currency_mismatch");
        if (source.Balance.Minor < amount.Minor) throw new DomainException("insufficient_funds");
        if (destination.Balance.Minor > Money.Maximum - amount.Minor) throw new DomainException("invalid_amount");
        return new TransferResult(source.Apply(-amount.Minor), destination.Apply(amount.Minor));
    }
}
