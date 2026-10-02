using Banking.Application;
using Banking.Domain;
using Npgsql;

namespace Banking.Infrastructure;

public sealed class PostgresInventory(NpgsqlDataSource db) : IInventoryStore
{
    public async Task<ProductView> Create(ProductRequest request, CancellationToken ct)
    {
        _ = new Inventory(request.Stock);
        if (request.Id == Guid.Empty) throw new DomainException("invalid_product");
        await using var command = db.CreateCommand("INSERT INTO products(id,stock) VALUES($1,$2) ON CONFLICT DO NOTHING");
        command.Parameters.AddWithValue(request.Id);
        command.Parameters.AddWithValue(request.Stock);
        if (await command.ExecuteNonQueryAsync(ct) != 1) throw new DomainException("product_exists");
        return new(request.Id, request.Stock, 0);
    }
    public async Task<ProductView> Read(Guid id, CancellationToken ct)
    {
        await using var command = db.CreateCommand("SELECT stock,version FROM products WHERE id=$1");
        command.Parameters.AddWithValue(id);
        await using var reader = await command.ExecuteReaderAsync(ct);
        if (!await reader.ReadAsync(ct)) throw new DomainException("product_not_found");
        return new(id, reader.GetInt32(0), reader.GetInt32(1));
    }
    public Task<ProductView> Reserve(Guid id, string actor, ReservationRequest request, CancellationToken ct) =>
        Mutate(id, actor, request.ReservationId, request.Quantity, request.ExpectedVersion, false, ct);
    public Task<ProductView> Cancel(Guid id, Guid reservationId, string actor, int expectedVersion, CancellationToken ct) =>
        Mutate(id, actor, reservationId, 0, expectedVersion, true, ct);
    private async Task<ProductView> Mutate(Guid id, string actor, Guid reservationId, int quantity, int expectedVersion, bool cancel, CancellationToken ct)
    {
        await using var connection = await db.OpenConnectionAsync(ct);
        await using var tx = await connection.BeginTransactionAsync(ct);
        int stock, version;
        await using (var command = PostgresLedger.Command(connection, tx, "SELECT stock,version FROM products WHERE id=$1 FOR UPDATE", id))
        await using (var reader = await command.ExecuteReaderAsync(ct))
        {
            if (!await reader.ReadAsync(ct)) throw new DomainException("product_not_found");
            stock = reader.GetInt32(0); version = reader.GetInt32(1);
        }
        var history = new List<Inventory.ReservationState>();
        await using (var command = PostgresLedger.Command(connection, tx, "SELECT id,quantity,cancelled,actor FROM reservations WHERE product_id=$1", id))
        await using (var reader = await command.ExecuteReaderAsync(ct))
        {
            while (await reader.ReadAsync(ct))
            {
                var existingId = reader.GetGuid(0);
                if (existingId == reservationId && reader.GetString(3) != actor) throw new DomainException("forbidden");
                history.Add(new(existingId, reader.GetInt32(1), reader.GetBoolean(2)));
            }
        }
        var inventory = Inventory.Restore(stock, version, history);
        if (cancel) inventory.Cancel(reservationId, expectedVersion);
        else inventory.Reserve(reservationId, quantity, expectedVersion);
        if (inventory.Version != version)
        {
            await using var update = PostgresLedger.Command(connection, tx, "UPDATE products SET stock=$1,version=$2 WHERE id=$3", inventory.Available, inventory.Version, id);
            await update.ExecuteNonQueryAsync(ct);
            if (cancel)
            {
                await using var release = PostgresLedger.Command(connection, tx, "UPDATE reservations SET cancelled=true WHERE id=$1 AND product_id=$2", reservationId, id);
                await release.ExecuteNonQueryAsync(ct);
            }
            else
            {
                await using var reserve = PostgresLedger.Command(connection, tx, "INSERT INTO reservations(id,product_id,quantity,actor) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING", reservationId, id, quantity, actor);
                if (await reserve.ExecuteNonQueryAsync(ct) != 1) throw new DomainException("reservation_conflict");
            }
        }
        await tx.CommitAsync(ct);
        return new(id, inventory.Available, inventory.Version);
    }
}
