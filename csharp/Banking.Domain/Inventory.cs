namespace Banking.Domain;

public sealed class Inventory
{
    public sealed record ReservationState(Guid Id, int Quantity, bool Cancelled);
    private readonly Dictionary<Guid, int> reservations = [];
    private readonly HashSet<Guid> cancelled = [];
    public int Available { get; private set; }
    public int Version { get; private set; }
    public Inventory(int stock)
    {
        if (stock < 0) throw new DomainException("invalid_stock");
        Available = stock;
    }
    public static Inventory Restore(int available, int version, IEnumerable<ReservationState> history)
    {
        if (version < 0) throw new DomainException("invalid_stock");
        var inventory = new Inventory(available) { Version = version };
        foreach (var item in history)
        {
            if (item.Id == Guid.Empty || item.Quantity <= 0 || !inventory.reservations.TryAdd(item.Id, item.Quantity))
                throw new DomainException("invalid_reservation");
            if (item.Cancelled) inventory.cancelled.Add(item.Id);
        }
        return inventory;
    }
    public void Reserve(Guid id, int quantity, int expectedVersion)
    {
        if (id == Guid.Empty || quantity <= 0) throw new DomainException("invalid_reservation");
        if (reservations.TryGetValue(id, out var previous))
        {
            if (previous != quantity || cancelled.Contains(id)) throw new DomainException("reservation_conflict");
            return;
        }
        if (Version != expectedVersion) throw new DomainException("version_conflict");
        if (Available < quantity) throw new DomainException("insufficient_stock");
        Available -= quantity;
        Version++;
        reservations.Add(id, quantity);
    }
    public void Cancel(Guid id, int expectedVersion)
    {
        if (cancelled.Contains(id)) return;
        if (Version != expectedVersion) throw new DomainException("version_conflict");
        if (!reservations.TryGetValue(id, out var quantity)) throw new DomainException("reservation_not_found");
        Available += quantity;
        cancelled.Add(id);
        Version++;
    }
}
