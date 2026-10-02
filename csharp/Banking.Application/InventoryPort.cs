namespace Banking.Application;

public sealed record ProductView(Guid Id, int Available, int Version);
public sealed record ProductRequest(Guid Id, int Stock);
public sealed record ReservationRequest(Guid ReservationId, int Quantity, int ExpectedVersion);
public interface IInventoryStore
{
    Task<ProductView> Create(ProductRequest request, CancellationToken ct);
    Task<ProductView> Read(Guid id, CancellationToken ct);
    Task<ProductView> Reserve(Guid id, string actor, ReservationRequest request, CancellationToken ct);
    Task<ProductView> Cancel(Guid id, Guid reservationId, string actor, int expectedVersion, CancellationToken ct);
}
