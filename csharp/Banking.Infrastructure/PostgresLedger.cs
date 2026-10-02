using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Banking.Application;
using Banking.Domain;
using Npgsql;

namespace Banking.Infrastructure;

public sealed class PostgresLedger(NpgsqlDataSource dataSource) : ILedger
{
    internal static NpgsqlCommand Command(NpgsqlConnection connection, NpgsqlTransaction? tx, string sql, params object[] values)
    {
        var command = new NpgsqlCommand(sql, connection, tx);
        foreach (var value in values) command.Parameters.Add(new NpgsqlParameter { Value = value });
        return command;
    }

    public async Task<AccountView> Open(CreateAccount request, CancellationToken ct)
    {
        var amount = new Money(request.OpeningMinor, request.Currency);
        if (request.Id == Guid.Empty || string.IsNullOrWhiteSpace(request.OwnerId)) throw new DomainException("invalid_account");
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using var tx = await connection.BeginTransactionAsync(ct);
        await using (var command = Command(connection, tx,
            "INSERT INTO accounts(id,owner_id,balance_minor,currency,version) VALUES($1,$2,$3,$4,1) ON CONFLICT DO NOTHING",
            request.Id, request.OwnerId, amount.Minor, amount.Currency))
        {
            if (await command.ExecuteNonQueryAsync(ct) != 1) throw new DomainException("account_exists");
        }
        await Append(connection, tx, new(request.Id, 1, amount.Minor, amount.Currency), ct);
        await tx.CommitAsync(ct);
        return new(request.Id, request.OwnerId, amount.Minor, amount.Currency, 1);
    }

    private static async Task Append(NpgsqlConnection connection, NpgsqlTransaction tx, AccountEvent entry, CancellationToken ct, Guid? transferId = null)
    {
        await using var command = Command(connection, tx,
            "INSERT INTO account_events(event_id,account_id,version,delta,currency,transfer_id) VALUES($1,$2,$3,$4,$5,$6)",
            Guid.NewGuid(), entry.AccountId, entry.Version, entry.Delta, entry.Currency);
        command.Parameters.Add(new NpgsqlParameter { NpgsqlDbType = NpgsqlTypes.NpgsqlDbType.Uuid, Value = (object?)transferId ?? DBNull.Value });
        await command.ExecuteNonQueryAsync(ct);
    }

    public async Task<Receipt> Transfer(string actor, Guid key, TransferCommand request, CancellationToken ct)
    {
        var fingerprint = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(
            $"{request.SourceId:D}|{request.DestinationId:D}|{request.AmountMinor}|{request.Currency}")));
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using var tx = await connection.BeginTransactionAsync(ct);
        // Serializes duplicate requests across processes, including a retry racing the original.
        await using (var mutex = Command(connection, tx, "SELECT pg_advisory_xact_lock(hashtextextended($1,0))", actor + ":" + key))
            await mutex.ExecuteNonQueryAsync(ct);
        await using (var existing = Command(connection, tx,
            "SELECT id,fingerprint,source_id,destination_id,amount_minor,currency FROM transfers WHERE actor=$1 AND request_key=$2", actor, key))
        await using (var reader = await existing.ExecuteReaderAsync(ct))
        {
            if (await reader.ReadAsync(ct))
            {
                if (reader.GetString(1) != fingerprint) throw new DomainException("idempotency_conflict");
                return new(reader.GetGuid(0), reader.GetGuid(2), reader.GetGuid(3), reader.GetInt64(4), reader.GetString(5));
            }
        }
        var accounts = new Dictionary<Guid, Account>();
        string? owner = null;
        await using (var locked = Command(connection, tx,
            "SELECT id,owner_id,balance_minor,currency,version FROM accounts WHERE id=$1 OR id=$2 ORDER BY id FOR UPDATE",
            request.SourceId, request.DestinationId))
        await using (var reader = await locked.ExecuteReaderAsync(ct))
        {
            while (await reader.ReadAsync(ct))
            {
                var id = reader.GetGuid(0);
                accounts[id] = new(id, new Money(reader.GetInt64(2), reader.GetString(3)), reader.GetInt32(4));
                if (id == request.SourceId) owner = reader.GetString(1);
            }
        }
        if (!accounts.ContainsKey(request.SourceId) || !accounts.ContainsKey(request.DestinationId)) throw new DomainException("account_not_found");
        if (owner != actor) throw new DomainException("forbidden");
        var result = Domain.Transfer.Execute(accounts[request.SourceId], accounts[request.DestinationId], new(request.AmountMinor, request.Currency));
        var receipt = new Receipt(Guid.NewGuid(), request.SourceId, request.DestinationId, request.AmountMinor, request.Currency);
        foreach (var entry in new[] { result.Debit, result.Credit })
        {
            await using var update = Command(connection, tx, "UPDATE accounts SET balance_minor=balance_minor+$1,version=$2 WHERE id=$3",
                entry.Delta, entry.Version, entry.AccountId);
            await update.ExecuteNonQueryAsync(ct);
            await Append(connection, tx, entry, ct, receipt.Id);
        }
        await using (var insert = Command(connection, tx,
            "INSERT INTO transfers(id,actor,request_key,fingerprint,source_id,destination_id,amount_minor,currency) VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
            receipt.Id, actor, key, fingerprint, receipt.SourceId, receipt.DestinationId, receipt.AmountMinor, receipt.Currency))
            await insert.ExecuteNonQueryAsync(ct);
        var eventId = Guid.NewGuid();
        var payload = JsonSerializer.Serialize(new { eventId, type = "TransferCompleted", schemaVersion = 1,
            transferId = receipt.Id, sourceId = receipt.SourceId, destinationId = receipt.DestinationId,
            amountMinor = receipt.AmountMinor, currency = receipt.Currency }, new JsonSerializerOptions(JsonSerializerDefaults.Web));
        await using (var outbox = Command(connection, tx, "INSERT INTO outbox(event_id,aggregate_id,payload) VALUES($1,$2,$3::jsonb)",
            eventId, receipt.SourceId, payload))
            await outbox.ExecuteNonQueryAsync(ct);
        await tx.CommitAsync(ct);
        return receipt;
    }

    public async Task<AccountView> Read(Guid id, string actor, bool admin, CancellationToken ct)
    {
        await using var command = dataSource.CreateCommand("SELECT owner_id,balance_minor,currency,version FROM accounts WHERE id=$1");
        command.Parameters.AddWithValue(id);
        await using var reader = await command.ExecuteReaderAsync(ct);
        if (!await reader.ReadAsync(ct)) throw new DomainException("account_not_found");
        if (!admin && reader.GetString(0) != actor) throw new DomainException("forbidden");
        return new(id, reader.GetString(0), reader.GetInt64(1), reader.GetString(2), reader.GetInt32(3));
    }
    public async Task<IReadOnlyList<AccountEvent>> History(Guid id, string actor, bool admin, CancellationToken ct)
    {
        _ = await Read(id, actor, admin, ct);
        await using var command = dataSource.CreateCommand("SELECT version,delta,currency FROM account_events WHERE account_id=$1 ORDER BY version");
        command.Parameters.AddWithValue(id);
        await using var reader = await command.ExecuteReaderAsync(ct);
        var events = new List<AccountEvent>();
        while (await reader.ReadAsync(ct)) events.Add(new(id, reader.GetInt32(0), reader.GetInt64(1), reader.GetString(2)));
        return events;
    }
}
